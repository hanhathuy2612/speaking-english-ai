import { AudioService } from '@/services/audio.service';
import { WsService, WsMessage } from '@/services/ws.service';
import { CommonModule } from '@angular/common';
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
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

export interface ChatMessage {
  role: 'user' | 'ai';
  text: string;
  partial?: boolean;
  /** User's recording (WebM) for replay */
  userAudio?: ArrayBuffer;
  /** AI TTS audio (MP3) for replay */
  aiAudio?: ArrayBuffer;
}

export interface TurnScore {
  fluency: number;
  vocabulary: number;
  grammar: number;
  overall: number;
  feedback: string;
}

@Component({
  selector: 'app-conversation',
  standalone: true,
  imports: [CommonModule, RouterLink],
  styleUrls: ['./conversation.component.scss'],
  templateUrl: './conversation.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConversationComponent implements OnDestroy, AfterViewChecked {
  private chatArea = viewChild<ElementRef<HTMLDivElement>>('chatArea');

  private ws = inject(WsService);
  private audio = inject(AudioService);
  private cdr = inject(ChangeDetectorRef);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  /** Route params as signal */
  private queryParams = toSignal(this.route.queryParams, {
    initialValue: {} as Record<string, string>,
  });

  topicId = computed(() => Number(this.queryParams()['topicId']) || 0);
  topicTitle = computed(() => this.queryParams()['title'] ?? 'Conversation');

  connected = toSignal(this.ws.connected$, { initialValue: false });
  vuLevel = toSignal(this.audio.volume$, { initialValue: 0 });

  recording = signal(false);
  aiSpeaking = signal(false);
  ttsEnabled = signal(true);
  errorMessage = signal('');
  messages = signal<ChatMessage[]>([]);
  scores = signal<Record<number, TurnScore>>({});
  /** Index of message whose audio is currently playing (-1 = none) */
  playingMessageIndex = signal(-1);

  private pendingAiMsgIndex = -1;
  private audioQueue: ArrayBuffer[] = [];
  private playingAudio = false;
  private partialUpdateScheduled = false;
  private lastUserRecording: ArrayBuffer | null = null;
  private currentAiAudioChunks: ArrayBuffer[] = [];
  private lastAiMessageIndex = -1;

  constructor() {
    // When route params change: navigate away if no topic, else connect
    effect(() => {
      const id = this.topicId();
      if (id <= 0) {
        this.router.navigate(['/topics']);
        return;
      }
      this.ws.connect(id);
    });

    // When connected and we have a topic, send start
    effect(() => {
      if (this.connected() && this.topicId() > 0) {
        this.ws.sendJson({ type: 'start', topicId: this.topicId() });
      }
    });

    // Process each WS message and update signals
    this.ws.messages$.pipe(takeUntilDestroyed()).subscribe((msg) => {
      this._handleMessage(msg);
      this._scheduleDetectChanges(msg as WsMessage);
    });
  }

  ngAfterViewChecked(): void {
    this.scrollToBottom();
  }

  ngOnDestroy(): void {
    this.ws.sendJson({ type: 'stop' });
    this.ws.disconnect();
    this.audio.release();
  }

  toggleTts(): void {
    this.ttsEnabled.update((v) => !v);
  }

  async startRecording(): Promise<void> {
    if (this.recording() || !this.connected()) return;
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

  private _handleMessage(msg: Record<string, unknown> & { type: string }): void {
    switch (msg['type']) {
      case 'status':
        this.errorMessage.set('');
        break;
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
      case 'assistant_partial': {
        const chunk = msg['text'] as string;
        const done = msg['done'] as boolean;
        const current = this.messages();
        if (this.pendingAiMsgIndex === -1) {
          this.currentAiAudioChunks = [];
          const newMsg: ChatMessage = { role: 'ai', text: chunk, partial: true };
          this.messages.update((m) => [...m, newMsg]);
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
            const idx = this.pendingAiMsgIndex;
            next[idx] = { ...next[idx], partial: false };
            return next;
          });
          this.lastAiMessageIndex = this.pendingAiMsgIndex;
          this.pendingAiMsgIndex = -1;
        }
        break;
      }
      case 'assistant_audio_end': {
        if (this.lastAiMessageIndex >= 0 && this.currentAiAudioChunks.length > 0) {
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
        this.currentAiAudioChunks = [];
        this.lastAiMessageIndex = -1;
        break;
      }
      case 'assistant_audio_chunk': {
        const b64 = msg['data'] as string;
        const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)).buffer;
        this.currentAiAudioChunks.push(bytes);
        if (this.ttsEnabled()) {
          this.audioQueue.push(bytes);
          if (!this.playingAudio) this._flushAudioQueue();
        }
        break;
      }
      case 'turn_score': {
        const list = this.messages();
        const lastUserIdx = [...list].reverse().findIndex((m) => m.role === 'user');
        if (lastUserIdx !== -1) {
          const idx = list.length - 1 - lastUserIdx;
          const score: TurnScore = {
            fluency: msg['fluency'] as number,
            vocabulary: msg['vocabulary'] as number,
            grammar: msg['grammar'] as number,
            overall: msg['overall'] as number,
            feedback: msg['feedback'] as string,
          };
          this.scores.update((s) => ({ ...s, [idx]: score }));
        }
        break;
      }
    }
  }

  private async _flushAudioQueue(): Promise<void> {
    this.playingAudio = true;
    this.aiSpeaking.set(true);
    this.cdr.detectChanges();
    while (this.audioQueue.length > 0) {
      const chunk = this.audioQueue.shift()!;
      try {
        await this.audio.playAudioBuffer(chunk);
      } catch {
        // Ignore decode errors for partial chunks
      }
    }
    this.playingAudio = false;
    this.aiSpeaking.set(false);
    this.cdr.detectChanges();
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

  async playMessageAudio(msg: ChatMessage, index: number, kind: 'user' | 'ai'): Promise<void> {
    const buf = kind === 'user' ? msg.userAudio : msg.aiAudio;
    if (!buf) return;
    this.audioQueue.length = 0;
    this.playingAudio = false;
    this.audio.stopPlayback();
    this.playingMessageIndex.set(index);
    this.cdr.detectChanges();
    try {
      await this.audio.playAudioBuffer(buf);
    } catch {
      // ignore decode errors
    }
    this.playingMessageIndex.set(-1);
    this.cdr.detectChanges();
  }

  /** Called from template after view check to scroll to bottom */
  scrollToBottom(): void {
    try {
      const el = this.chatArea()?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    } catch {
      // ignore
    }
  }
}
