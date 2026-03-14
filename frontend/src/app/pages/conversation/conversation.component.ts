import { ApiService } from '@/services/api.service';
import { AudioService } from '@/services/audio.service';
import { WsService, WsMessage } from '@/services/ws.service';
import { NgOptionTemplateDirective, NgSelectComponent } from '@ng-select/ng-select';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  AfterViewChecked,
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  computed,
  effect,
  ElementRef,
  inject,
  OnDestroy,
  OnInit,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

// ─── Types ─────────────────────────────────────────────────────────────────

export interface ChatMessage {
  role: 'user' | 'ai';
  text: string;
  partial?: boolean;
  userAudio?: ArrayBuffer;
  aiAudio?: ArrayBuffer;
  /** Set for AI messages when we have a saved turn (from history or turn_score) */
  turnId?: number;
  /** Saved guideline for this AI question (from history or after fetching) */
  guideline?: string;
}

export interface TurnScore {
  fluency: number;
  vocabulary: number;
  grammar: number;
  overall: number;
  feedback: string;
}

interface StartPayload {
  type: 'start';
  topicId: number;
  ttsRate: string;
  ttsVoice: string;
  sessionId?: number;
}

const TTS_RATE_OPTIONS = ['-30%', '-20%', '-10%', '+0%', '+10%', '+20%', '+30%'];
const LEVEL_OPTIONS = [
  { value: '', label: 'General' },
  ...['A1', 'A2', 'B1', 'B2', 'C1'].map((l) => ({ value: l, label: l })),
];
const NOOP = { next: () => {}, error: () => {} };

// ─── Component ─────────────────────────────────────────────────────────────

@Component({
  selector: 'app-conversation',
  standalone: true,
  imports: [CommonModule, FormsModule, NgSelectComponent, NgOptionTemplateDirective, RouterLink],
  styleUrls: ['./conversation.component.scss'],
  templateUrl: './conversation.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConversationComponent implements OnInit, OnDestroy, AfterViewChecked {
  // Injectables & view refs
  private readonly ws = inject(WsService);
  private readonly audio = inject(AudioService);
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  private readonly chatArea = viewChild<ElementRef<HTMLDivElement>>('chatArea');

  private readonly queryParams = toSignal(this.route.queryParams, {
    initialValue: {} as Record<string, string>,
  });

  // Route-derived state (use snapshot when queryParams not yet emitted so effect doesn't redirect with id=0)
  topicId = computed(() => {
    const q = this.queryParams();
    const snap = this.route.snapshot.queryParams;
    return Number(q['topicId']) || Number(snap['topicId']) || 0;
  });
  topicTitle = computed(
    () => this.queryParams()['title'] ?? this.route.snapshot.queryParams['title'] ?? 'Conversation',
  );
  sessionId = computed(() => {
    const s = this.queryParams()['sessionId'] ?? this.route.snapshot.queryParams['sessionId'];
    return s ? Number(s) : 0;
  });

  // Connection & UI state
  connected = toSignal(this.ws.connected$, { initialValue: false });
  reconnecting = toSignal(this.ws.reconnecting$, { initialValue: false });
  vuLevel = toSignal(this.audio.volume$, { initialValue: 0 });
  canRecord = computed(() => this.connected() && !this.aiSpeaking() && this.messages().length > 0);

  recording = signal(false);
  aiSpeaking = signal(false);
  messages = signal<ChatMessage[]>([]);
  scores = signal<Record<number, TurnScore>>({});
  errorMessage = signal('');
  deviceChangedNotice = signal('');
  playingMessageIndex = signal(-1);

  /** Message selected for guidance panel (index + message); null = panel closed */
  selectedForGuide = signal<{ index: number; message: ChatMessage } | null>(null);
  /** Suggestions from API for the selected question; empty while loading or none */
  guideSuggestions = signal<string[]>([]);
  guideLoading = signal(false);

  // TTS
  ttsEnabled = signal(true);
  ttsRate = signal('+0%');
  ttsVoice = signal('en-US-JennyNeural');
  ttsVoices = signal<{ id: string; name: string }[]>([]);
  previewingVoiceId = signal<string | null>(null);
  readonly ttsRateOptions = TTS_RATE_OPTIONS;

  // Level (real-time override for AI response length/complexity)
  conversationLevel = signal('');
  readonly levelOptions = LEVEL_OPTIONS;

  // Private state
  private pendingAiMsgIndex = -1;
  private lastAiMessageIndex = -1;
  private currentAiAudioChunks: ArrayBuffer[] = [];
  private lastUserRecording: ArrayBuffer | null = null;
  private partialUpdateScheduled = false;
  private userPrefsApplied = signal(false);
  private startSentForConnection = false;

  constructor() {
    this._effectLoadPrefsAndConnect();
    this._effectSendStartWhenReady();
    this.ws.messages$.pipe(takeUntilDestroyed()).subscribe((msg) => {
      this._handleMessage(msg as Record<string, unknown> & { type: string });
      this._scheduleDetectChanges(msg as WsMessage);
    });
    this.audio.deviceLostDuringRecording$
      .pipe(takeUntilDestroyed())
      .subscribe(() => this._onDeviceLostDuringRecording());
  }

  private _effectLoadPrefsAndConnect(): void {
    effect(() => {
      const id = this.topicId();
      if (id <= 0) {
        this.router.navigate(['/topics']);
        return;
      }
      this.messages.set([]);
      this.scores.set({});
      this.startSentForConnection = false;
      this.userPrefsApplied.set(false);
      this.api.getMe().subscribe({
        next: (me) => {
          const voice = me.tts_voice ?? (me as Record<string, unknown>)['ttsVoice'];
          const rate = me.tts_rate ?? (me as Record<string, unknown>)['ttsRate'];
          if (voice != null && String(voice).trim() !== '') this.ttsVoice.set(String(voice));
          if (rate != null && String(rate).trim() !== '') this.ttsRate.set(String(rate));
          this.userPrefsApplied.set(true);
          this.ws.connect(id);
          this.cdr.detectChanges();
        },
        error: () => {
          this.userPrefsApplied.set(true);
          this.ws.connect(id);
        },
      });
    });
  }

  private _effectSendStartWhenReady(): void {
    effect(() => {
      const conn = this.connected();
      const prefsApplied = this.userPrefsApplied();
      const topicId = this.topicId();
      const sessionId = this.sessionId();
      if (!conn || !prefsApplied || topicId <= 0) {
        if (!conn) this.startSentForConnection = false;
        return;
      }
      if (this.startSentForConnection) return;
      this.startSentForConnection = true;
      const payload: StartPayload = {
        type: 'start',
        topicId,
        ttsRate: this.ttsRate(),
        ttsVoice: this.ttsVoice(),
      };
      if (sessionId > 0) payload.sessionId = sessionId;
      this.ws.sendJson(payload);
    });
  }

  ngOnInit(): void {
    this.api.getTtsVoices().subscribe({
      next: (list) => this.ttsVoices.set(list.map((v) => ({ id: v.id, name: v.name }))),
      error: () => {},
    });
  }

  ngAfterViewChecked(): void {
    this._scrollToBottom();
  }

  ngOnDestroy(): void {
    this._clearAudioPlayback();
    this.audio.release();
    this.ws.sendJson({ type: 'stop' });
    this.ws.disconnect();
  }

  // ─── TTS ─────────────────────────────────────────────────────────────────

  onTtsRateChange(rate: string): void {
    this.ttsRate.set(rate);
    this.api.patchMe({ tts_rate: rate }).subscribe(NOOP);
    this._sendTtsPreferences(rate, this.ttsVoice());
  }

  onTtsVoiceChange(voiceId: string): void {
    this.ttsVoice.set(voiceId);
    this.api.patchMe({ tts_voice: voiceId }).subscribe(NOOP);
    this._sendTtsPreferences(this.ttsRate(), voiceId);
  }

  getVoiceName(voiceId: string): string {
    const v = this.ttsVoices().find((x) => x.id === voiceId);
    return v?.name ?? voiceId ?? 'Select…';
  }

  async previewVoice(voiceId: string): Promise<void> {
    this.previewingVoiceId.set(voiceId);
    this._clearAudioPlayback();
    this.audio.stopPlayback();
    try {
      const blob = await firstValueFrom(this.api.getTtsPreview(voiceId, this.ttsRate()));
      await this.audio.playAudioBuffer(await blob.arrayBuffer());
    } catch {
      // ignore
    } finally {
      this.previewingVoiceId.set(null);
    }
  }

  toggleTts(): void {
    this.ttsEnabled.update((v) => !v);
  }

  onLevelChange(level: string | null): void {
    const value = level ?? '';
    this.conversationLevel.set(value);
    if (this.connected()) {
      this.ws.sendJson({ type: 'set_level', level: value });
    }
  }

  openGuidePanel(message: ChatMessage, index: number): void {
    this.selectedForGuide.set({ index, message });
    const question = message.text?.trim() || '';
    if (!question) {
      this.guideSuggestions.set(['No question text.']);
      this.guideLoading.set(false);
      return;
    }
    if (message.guideline) {
      this.guideSuggestions.set(message.guideline.split('\n').filter(Boolean));
      this.guideLoading.set(false);
      this.cdr.detectChanges();
      return;
    }
    this.guideSuggestions.set([]);
    this.guideLoading.set(true);
    this.api.getGuidance(question, message.turnId).subscribe({
      next: (res) => {
        const suggestions = res.suggestions || [];
        this.guideSuggestions.set(suggestions);
        if (message.turnId != null && suggestions.length > 0) {
          this.messages.update((list) => {
            const next = [...list];
            if (next[index]) next[index] = { ...next[index], guideline: suggestions.join('\n') };
            return next;
          });
        }
        this.guideLoading.set(false);
        this.cdr.detectChanges();
      },
      error: () => {
        this.guideSuggestions.set(['Could not load suggestions. Try again.']);
        this.guideLoading.set(false);
        this.cdr.detectChanges();
      },
    });
  }

  closeGuidePanel(): void {
    this.selectedForGuide.set(null);
    this.guideSuggestions.set([]);
    this.guideLoading.set(false);
  }

  private _sendTtsPreferences(rate?: string, voice?: string): void {
    if (!this.connected()) return;
    this.ws.sendJson({
      type: 'tts_preferences',
      ttsRate: rate ?? this.ttsRate(),
      ttsVoice: voice ?? this.ttsVoice(),
    });
  }

  // ─── Recording ──────────────────────────────────────────────────────────

  async startRecording(): Promise<void> {
    if (this.recording() || !this.canRecord()) return;
    this.recording.set(true);
    await this.audio.startRecording((buf) => {
      this.lastUserRecording = buf;
      this.ws.sendBinary(buf);
    });
  }

  async stopRecording(): Promise<void> {
    if (!this.recording()) return;
    this.recording.set(false);
    await this.audio.stopRecording();
    this.ws.sendJson({ type: 'audio_end' });
  }

  // ─── Playback ────────────────────────────────────────────────────────────

  async playMessageAudio(msg: ChatMessage, index: number, kind: 'user' | 'ai'): Promise<void> {
    const buf = kind === 'user' ? msg.userAudio : msg.aiAudio;
    if (!buf) return;
    if (this.playingMessageIndex() === index) {
      this._clearAudioPlayback();
      this.audio.stopPlayback();
      this.playingMessageIndex.set(-1);
      this.cdr.detectChanges();
      return;
    }
    this._clearAudioPlayback();
    this.audio.stopPlayback();
    this.playingMessageIndex.set(index);
    this.cdr.detectChanges();
    try {
      await this.audio.playAudioBuffer(buf);
    } catch {
      // ignore
    }
    this.playingMessageIndex.set(-1);
    this.cdr.detectChanges();
  }

  // ─── Message handling & helpers ───────────────────────────────────────────

  private _onDeviceLostDuringRecording(): void {
    if (!this.recording()) return;
    this.recording.set(false);
    this.cdr.detectChanges();
    this.audio.stopRecording().then(() => {
      this.ws.sendJson({ type: 'audio_end' });
      this.errorMessage.set('');
      this.deviceChangedNotice.set('Microphone changed. You can hold to speak again.');
      this.cdr.detectChanges();
      setTimeout(() => {
        this.deviceChangedNotice.set('');
        this.cdr.detectChanges();
      }, 4000);
    });
  }

  private _handleMessage(msg: Record<string, unknown> & { type: string }): void {
    switch (msg['type']) {
      case 'status': {
        this.errorMessage.set('');
        const message = msg['message'] as string | undefined;
        if (message === 'session_started') {
          const topicLevel = msg['topicLevel'] as string | undefined;
          if (topicLevel != null && typeof topicLevel === 'string') {
            const normalized = topicLevel.trim();
            this.conversationLevel.set(normalized);
          }
        }
        break;
      }
      case 'history': {
        const list =
          (msg['messages'] as {
            role: string;
            text: string;
            turnId?: number;
            guideline?: string;
          }[]) ?? [];
        this.messages.set(
          list.map((m) => ({
            role: m.role === 'user' ? 'user' : 'ai',
            text: m.text,
            ...(m.role === 'assistant' && {
              turnId: m.turnId,
              guideline: m.guideline ?? undefined,
            }),
          })),
        );
        break;
      }
      case 'error':
        this.errorMessage.set((msg['message'] as string) || 'Something went wrong');
        break;
      case 'user_transcript': {
        const text = msg['text'] as string;
        const userMsg: ChatMessage = { role: 'user', text };
        if (this.lastUserRecording) {
          userMsg.userAudio = this.lastUserRecording;
          this.lastUserRecording = null;
        }
        this.messages.update((m) => [...m, userMsg]);
        this.pendingAiMsgIndex = -1;
        break;
      }
      case 'assistant_partial':
        this._handleAssistantPartial(msg);
        break;
      case 'assistant_audio_end':
        this._applyAiAudioToLastMessage();
        this.currentAiAudioChunks = [];
        this.lastAiMessageIndex = -1;
        this.audio.endStreamingPlayback().then(() => {
          this.aiSpeaking.set(false);
          this.cdr.detectChanges();
        });
        break;
      case 'assistant_audio_chunk': {
        const b64 = msg['data'] as string;
        const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)).buffer;
        this.currentAiAudioChunks.push(bytes);
        if (this.ttsEnabled()) {
          if (this.currentAiAudioChunks.length === 1) this.audio.stopPlayback();
          this.audio.enqueueStreamingChunk(bytes);
          this.aiSpeaking.set(true);
          this.cdr.detectChanges();
        }
        break;
      }
      case 'turn_score':
        this._handleTurnScore(msg);
        break;
    }
  }

  private _handleAssistantPartial(msg: Record<string, unknown>): void {
    const chunk = msg['text'] as string;
    const done = msg['done'] as boolean;
    const current = this.messages();
    if (this.pendingAiMsgIndex === -1) {
      this.currentAiAudioChunks = [];
      this.messages.update((m) => [...m, { role: 'ai', text: chunk, partial: true }]);
      this.pendingAiMsgIndex = current.length;
    } else {
      this.messages.update((m) => {
        const next = [...m];
        const idx = this.pendingAiMsgIndex;
        next[idx] = { ...next[idx], text: next[idx].text + chunk };
        return next;
      });
    }
    if (done) {
      this.messages.update((m) => {
        const next = [...m];
        next[this.pendingAiMsgIndex] = { ...next[this.pendingAiMsgIndex], partial: false };
        return next;
      });
      this.lastAiMessageIndex = this.pendingAiMsgIndex;
      this.pendingAiMsgIndex = -1;
    }
  }

  private _applyAiAudioToLastMessage(): void {
    if (this.lastAiMessageIndex < 0 || this.currentAiAudioChunks.length === 0) return;
    const total = this.currentAiAudioChunks.reduce((s, c) => s + c.byteLength, 0);
    const out = new Uint8Array(total);
    let offset = 0;
    for (const c of this.currentAiAudioChunks) {
      out.set(new Uint8Array(c), offset);
      offset += c.byteLength;
    }
    const idx = this.lastAiMessageIndex;
    this.messages.update((m) => {
      const next = [...m];
      next[idx] = { ...next[idx], aiAudio: out.buffer };
      return next;
    });
  }

  private _handleTurnScore(msg: Record<string, unknown>): void {
    const list = this.messages();
    const lastUserIdx = [...list].reverse().findIndex((m) => m.role === 'user');
    if (lastUserIdx === -1) return;
    const idx = list.length - 1 - lastUserIdx;
    this.scores.update((s) => ({
      ...s,
      [idx]: {
        fluency: msg['fluency'] as number,
        vocabulary: msg['vocabulary'] as number,
        grammar: msg['grammar'] as number,
        overall: msg['overall'] as number,
        feedback: msg['feedback'] as string,
      },
    }));
    const turnId = msg['turnId'] as number | undefined;
    if (turnId != null && idx + 1 < list.length) {
      this.messages.update((m) => {
        const next = [...m];
        next[idx + 1] = { ...next[idx + 1], turnId };
        return next;
      });
    }
  }

  private _scheduleDetectChanges(msg: WsMessage): void {
    if (msg['type'] === 'assistant_partial') {
      if (msg['done'] === true) {
        this.cdr.detectChanges();
        return;
      }
      if (!this.partialUpdateScheduled) {
        this.partialUpdateScheduled = true;
        setTimeout(() => {
          this.partialUpdateScheduled = false;
          this.cdr.detectChanges();
        }, 50);
      }
    } else {
      this.cdr.detectChanges();
    }
  }

  private _clearAudioPlayback(): void {
    this.audio.stopPlayback();
  }

  scrollToBottom(): void {
    this._scrollToBottom();
  }

  private _scrollToBottom(): void {
    try {
      const el = this.chatArea()?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    } catch {
      // ignore
    }
  }
}
