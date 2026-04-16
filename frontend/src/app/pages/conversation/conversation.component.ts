import { AccountService } from '@/app/shared/services/account.service';
import { ApiService, UnitStepSummary } from '@/services/api.service';
import { AudioService } from '@/services/audio.service';
import { WsMessage, WsService } from '@/services/ws.service';
import { CommonModule } from '@angular/common';
import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  computed,
  effect,
  inject,
  OnDestroy,
  OnInit,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { finalize, firstValueFrom } from 'rxjs';
import { applyAssistantPartialFrame, attachConcatenatedAiAudio } from './audio/assistant-stream';
import { parseGuidelineSections, stringifyGuidelineSections } from './audio/guidelines';
import { ConversationControlsComponent } from './conversation-controls/conversation-controls.component';
import { ConversationGuidePanelComponent } from './conversation-guide-panel/conversation-guide-panel.component';
import { ConversationHeaderComponent } from './conversation-header/conversation-header.component';
import { ConversationMessageListComponent } from './conversation-message-list/conversation-message-list.component';
import { ConversationUnitBannerComponent } from './conversation-unit-banner/conversation-unit-banner.component';
import { ConversationUnitCompleteModalComponent } from './conversation-unit-complete-modal/conversation-unit-complete-modal.component';
import { mapSessionDetailTurnsToMessages } from './mappers/session.mapper';
import { mergeTurnSavedIntoMessages } from './mappers/turn-saved.merge';
import { CHAT_ROLE_AI, CHAT_ROLE_USER } from './model/chat-roles';
import {
  GUIDE_PANEL_DEFAULT_W,
  GUIDE_PANEL_MAX_W,
  GUIDE_PANEL_MIN_W,
  GUIDE_PANEL_WIDTH_LS,
  NOOP,
} from './model/constants';
import type { ChatMessage, SessionScoreTurn, TopicUnitWsMeta } from './model/models';
import { mergeTurnScoresAndSessionFeedback } from './scoring/session-scoring';
import { ConversationWsStartPayload } from './ws/helpers';
import {
  WS_STATUS_SESSION_STARTED,
  WS_TYPE_ASSISTANT_PARTIAL,
  WS_TYPE_AUDIO_END,
  WS_TYPE_REWORK,
  WS_TYPE_SET_LEVEL,
  WS_TYPE_START,
  WS_TYPE_TTS_PREFERENCES,
  WS_TYPE_USER_TEXT,
} from './ws/protocol';
import { routeConversationWsMessage, type ConversationWsSink } from './ws/router';

/** Matches backend `GuidanceRequest.prior_context` max_length; trim oldest lines if exceeded. */
const GUIDANCE_PRIOR_CONTEXT_MAX_CHARS = 10_000;
const GUIDE_PANEL_MODE_GUIDE = 'guide' as const;
const API_AUDIO_KIND_USER = 'user' as const;
const API_AUDIO_KIND_ASSISTANT = 'assistant' as const;

function priorContextLinesBeforeIndex(
  messages: readonly ChatMessage[],
  endExclusive: number,
): string {
  const lines: string[] = [];
  for (let i = 0; i < endExclusive && i < messages.length; i++) {
    const m = messages[i];
    if (m.partial) continue;
    const t = m.text?.trim() ?? '';
    if (!t) continue;
    const label = m.role === CHAT_ROLE_USER ? 'Learner' : 'Tutor';
    lines.push(`${label}: ${t}`);
  }
  let s = lines.join('\n');
  if (s.length > GUIDANCE_PRIOR_CONTEXT_MAX_CHARS) {
    s = '…\n' + s.slice(-(GUIDANCE_PRIOR_CONTEXT_MAX_CHARS - 2));
  }
  return s;
}

@Component({
  selector: 'app-conversation',
  standalone: true,
  imports: [
    CommonModule,
    ConversationHeaderComponent,
    ConversationUnitBannerComponent,
    ConversationUnitCompleteModalComponent,
    ConversationGuidePanelComponent,
    ConversationMessageListComponent,
    ConversationControlsComponent,
  ],
  styleUrls: ['./conversation.component.scss'],
  templateUrl: './conversation.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConversationComponent implements OnInit, OnDestroy {
  private readonly ws = inject(WsService);
  private readonly audio = inject(AudioService);
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly accountService = inject(AccountService);

  private readonly messageList = viewChild(ConversationMessageListComponent);

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

  /** Guided roadmap step (optional). Omitted for free conversation. */
  unitId = computed(() => {
    const q = this.queryParams();
    const snap = this.route.snapshot.queryParams;
    const raw = q['unitId'] ?? snap['unitId'];
    const n = raw != null && raw !== '' ? Number(raw) : 0;
    return Number.isFinite(n) && n > 0 ? n : 0;
  });

  connected = toSignal(this.ws.connected$, { initialValue: false });
  reconnecting = toSignal(this.ws.reconnecting$, { initialValue: false });
  vuLevel = toSignal(this.audio.volume$, { initialValue: 0 });
  canRecord = computed(
    () =>
      !this.sessionArchiveView() &&
      this.connected() &&
      !this.aiSpeaking() &&
      this.messages().length > 0,
  );

  /** Ended session: show transcript from API only, no WebSocket. */
  sessionArchiveView = signal(false);
  sessionDetailLoading = signal(false);
  private _sessionBootstrapGen = 0;
  /** When we merge sessionId into the URL after start, skip one full bootstrap (avoid wipe + reconnect). */
  private _skipBootstrapForSessionUrlSync: { topicId: number; sessionId: number } | null = null;
  private _newConversationInFlight = false;

  recording = signal(false);
  transcribing = signal(false);
  aiSpeaking = signal(false);
  messages = signal<ChatMessage[]>([]);
  errorMessage = signal('');
  deviceChangedNotice = signal('');
  playingMessageIndex = signal(-1);

  selectedForGuide = signal<{ index: number; message: ChatMessage } | null>(null);
  guidePanelMode = signal<'guide' | 'optimize'>(GUIDE_PANEL_MODE_GUIDE);
  guideSuggestions = signal<string[]>([]);
  guideLoading = signal(false);
  guidePanelWidthPx = signal(GUIDE_PANEL_DEFAULT_W);
  guidePanelSidebarDesktop = signal(
    typeof matchMedia !== 'undefined' && matchMedia('(min-width: 768px)').matches,
  );

  ttsEnabled = signal(true);
  ttsRate = signal('+0%');
  ttsVoice = signal('en-US-JennyNeural');
  ttsVoices = signal<{ id: string; name: string }[]>([]);
  previewingVoiceId = signal<string | null>(null);

  conversationLevel = signal('');

  chatInput = signal('');
  private pendingAiMsgIndex = -1;
  private lastAiMessageIndex = -1;
  private currentAiAudioChunks: ArrayBuffer[] = [];
  private preTextAiAudioChunks: ArrayBuffer[] = [];
  private preTextAiAudioEnded = false;
  private lastUserRecording: ArrayBuffer | null = null;
  private partialUpdateScheduled = false;
  private readonly userPrefsApplied = signal(false);
  private startSentForConnection = false;
  private readonly _mqMinNav =
    typeof matchMedia === 'undefined' ? null : matchMedia('(min-width: 768px)');
  private _mqMinNavOff: (() => void) | null = null;
  private _guideResizeAbort: (() => void) | null = null;
  private _unitBannerTrackedId: number | null = null;

  liveSessionId = signal(0);
  unitStepMeta = signal<TopicUnitWsMeta | null>(null);
  unitBannerCollapsed = signal(false);
  feedbackRequestPending = signal(false);
  sessionEndedWithFeedback = signal(false);
  unitCompleteSummary = signal<UnitStepSummary | null>(null);
  /** Number of user turns sent but not yet acknowledged by turn_saved. */
  pendingTurnSaves = signal(0);

  endConversationFeedbackEnabled = computed(() => {
    if (this.sessionEndedWithFeedback()) return false;
    if (this.feedbackRequestPending()) return false;
    if (this.pendingTurnSaves() > 0) return false;
    if (!this.connected()) return false;
    const sid = this._activeSessionId();
    if (sid <= 0) return false;
    const msgs = this.messages();
    if (msgs.length === 0) return false;
    const last = msgs.at(-1);
    if (last?.role !== CHAT_ROLE_AI || last?.partial) return false;
    if (this.aiSpeaking() || this.recording() || this.transcribing()) return false;
    return true;
  });

  private readonly _wsSink: ConversationWsSink = {
    statusRouter: {
      clearError: () => this.errorMessage.set(''),
      setErrorMessage: (msg) => this.errorMessage.set(msg),
      applyTopicLevelAndSessionId: (m) => this._applyTopicLevelAndLiveSession(m),
      setUnitStepMeta: (meta) => this.unitStepMeta.set(meta),
      getLiveSessionId: () => this.liveSessionId(),
      fetchUnitStepSummary: (id) => this._fetchUnitStepSummary(id),
      setTranscribing: (v) => this.transcribing.set(v),
    },
    resetStreamingState: () => this._resetConversationStreamingState(),
    setMessages: (messages) => this.messages.set(messages),
    setTranscribing: (v) => this.transcribing.set(v),
    setErrorMessage: (s) => this.errorMessage.set(s),
    onUserTranscript: (text, userAudio) => this._onWsUserTranscript(text, userAudio),
    onAssistantPartial: (chunk, done) => this._onWsAssistantPartial(chunk, done),
    onAssistantAudioEnd: () => this._onWsAssistantAudioEnd(),
    onAssistantAudioChunk: (bytes) => this._onWsAssistantAudioChunk(bytes),
    onSessionScores: (turns, sessionFeedback) => this._onWsSessionScores(turns, sessionFeedback),
    onTurnSaved: (assistantMessageId, userMessageId, hasUserAudio, indexInSession) =>
      this._onWsTurnSaved(assistantMessageId, userMessageId, hasUserAudio, indexInSession),
  };

  constructor() {
    this._effectLoadPrefsAndConnect();
    this._effectSendStartWhenReady();
    this._effectUnitBannerResetOnStepChange();
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
      const sid = this.sessionId();
      if (id <= 0) {
        void this.router.navigate(['/topics']);
        return;
      }
      const skip = this._skipBootstrapForSessionUrlSync;
      if (skip) {
        if (skip.topicId === id && skip.sessionId === sid && sid > 0) {
          this._skipBootstrapForSessionUrlSync = null;
          return;
        }
        this._skipBootstrapForSessionUrlSync = null;
      }
      const gen = ++this._sessionBootstrapGen;
      this.messages.set([]);
      this.sessionEndedWithFeedback.set(false);
      this.pendingTurnSaves.set(0);
      this.startSentForConnection = false;
      this.userPrefsApplied.set(false);
      this.liveSessionId.set(0);
      this.unitStepMeta.set(null);
      this.unitCompleteSummary.set(null);
      this.sessionArchiveView.set(false);
      this.errorMessage.set('');

      if (sid > 0) {
        this.sessionDetailLoading.set(true);
        this.api.getSessionDetail(sid).subscribe({
          next: (detail) => {
            if (gen !== this._sessionBootstrapGen) return;
            this.sessionDetailLoading.set(false);
            if (detail.topic_id !== id) {
              this.errorMessage.set('This session does not belong to this topic.');
              this.cdr.markForCheck();
              return;
            }
            const ended = detail.ended_at != null && String(detail.ended_at).trim() !== '';
            if (ended) {
              this.sessionArchiveView.set(true);
              this.messages.set(
                mapSessionDetailTurnsToMessages(
                  detail.turns,
                  detail.opening_message,
                  detail.has_opening_audio,
                  detail.session_feedback,
                ),
              );
              this.sessionEndedWithFeedback.set(true);
              this.liveSessionId.set(sid);
              this.userPrefsApplied.set(true);
              this.startSentForConnection = true;
              this.accountService.getMe().subscribe({
                next: (me) => {
                  if (gen !== this._sessionBootstrapGen) return;
                  this._applyAccountTtsToSignals(me);
                  this.cdr.detectChanges();
                },
                error: () => {
                  if (gen !== this._sessionBootstrapGen) return;
                  this.cdr.detectChanges();
                },
              });
              this.cdr.detectChanges();
              return;
            }
            this._connectLiveAfterPrefs(id, gen);
          },
          error: () => {
            if (gen !== this._sessionBootstrapGen) return;
            this.sessionDetailLoading.set(false);
            this.errorMessage.set('Could not load this session. It may have been deleted.');
            this.cdr.markForCheck();
          },
        });
      } else {
        this.sessionDetailLoading.set(false);
        this._connectLiveAfterPrefs(id, gen);
      }
    });
  }

  private _connectLiveAfterPrefs(topicId: number, gen: number): void {
    this.accountService.getMe().subscribe({
      next: (me) => {
        if (gen !== this._sessionBootstrapGen) return;
        this._applyAccountTtsToSignals(me);
        this.userPrefsApplied.set(true);
        this.ws.connect(topicId);
        this.cdr.detectChanges();
      },
      error: () => {
        if (gen !== this._sessionBootstrapGen) return;
        this.userPrefsApplied.set(true);
        this.ws.connect(topicId);
        this.cdr.detectChanges();
      },
    });
  }

  private _effectUnitBannerResetOnStepChange(): void {
    effect(() => {
      const meta = this.unitStepMeta();
      const id = meta?.id ?? null;
      if (id === this._unitBannerTrackedId) return;
      this._unitBannerTrackedId = id;
      this.unitBannerCollapsed.set(false);
    });
  }

  private _effectSendStartWhenReady(): void {
    effect(() => {
      if (this.sessionArchiveView()) return;
      const conn = this.connected();
      const prefsApplied = this.userPrefsApplied();
      const topicId = this.topicId();
      const routeSessionId = this.sessionId();
      const resumeSessionId = routeSessionId > 0 ? routeSessionId : this.liveSessionId();
      const unitId = this.unitId();
      if (!conn || !prefsApplied || topicId <= 0) {
        if (!conn) this.startSentForConnection = false;
        return;
      }
      if (this.startSentForConnection) return;
      this.startSentForConnection = true;
      const payload: ConversationWsStartPayload = {
        type: WS_TYPE_START,
        topicId,
        ttsRate: this.ttsRate(),
        ttsVoice: this.ttsVoice(),
      };
      const bandOverride = this.conversationLevel().trim();
      if (bandOverride !== '') {
        payload.level = bandOverride;
      }
      if (resumeSessionId > 0) payload.sessionId = resumeSessionId;
      else if (unitId > 0) payload.unitId = unitId;
      this.ws.sendJson(payload);
    });
  }

  ngOnInit(): void {
    try {
      const raw = localStorage.getItem(GUIDE_PANEL_WIDTH_LS);
      if (raw) {
        const n = Number(raw);
        if (Number.isFinite(n)) {
          this.guidePanelWidthPx.set(
            Math.min(GUIDE_PANEL_MAX_W, Math.max(GUIDE_PANEL_MIN_W, Math.round(n))),
          );
        }
      }
    } catch {
      /* ignore */
    }

    if (this._mqMinNav) {
      const onMq = () => {
        this.guidePanelSidebarDesktop.set(this._mqMinNav!.matches);
        this.cdr.markForCheck();
      };
      this._mqMinNav.addEventListener('change', onMq);
      this._mqMinNavOff = () => this._mqMinNav!.removeEventListener('change', onMq);
    }

    this.api.getTtsVoices().subscribe({
      next: (list) => this.ttsVoices.set(list.map((v) => ({ id: v.id, name: v.name }))),
      error: () => {},
    });
  }

  ngOnDestroy(): void {
    this._mqMinNavOff?.();
    this._mqMinNavOff = null;
    this._endGuidePanelResize();
    this.feedbackRequestPending.set(false);
    this.audio.stopPlayback();
    this.audio.release();
    if (!this.sessionArchiveView()) {
      // Avoid WS `stop`: it finalizes the session. Back/navigate away only closes the socket.
      this.ws.disconnect();
    }
  }

  /** Fresh chat for the current topic (same as header “New conversation”). */
  goNewConversationSameTopic(): void {
    if (this._newConversationInFlight) return;
    const tid = this.topicId();
    const uid = this.unitId();
    this._newConversationInFlight = true;
    this.errorMessage.set('');
    this.api
      .postCreateSession({
        topic_id: tid,
        topic_unit_id: uid > 0 ? uid : null,
      })
      .pipe(
        finalize(() => {
          this._newConversationInFlight = false;
          this.cdr.markForCheck();
        }),
      )
      .subscribe({
        next: (res) => {
          const qp: Record<string, string | number> = {
            topicId: tid,
            title: this.topicTitle(),
            sessionId: res.id,
          };
          if (uid > 0) qp['unitId'] = uid;
          void this.router.navigate(['/conversation'], { queryParams: qp });
        },
        error: (err: { error?: { detail?: unknown } }) => {
          const d = err?.error?.detail;
          let msg = 'Could not start a new conversation.';
          if (typeof d === 'string') msg = d;
          else if (
            Array.isArray(d) &&
            d.length > 0 &&
            typeof (d[0] as { msg?: string }).msg === 'string'
          ) {
            msg = (d[0] as { msg: string }).msg;
          }
          this.errorMessage.set(msg);
          this.cdr.markForCheck();
        },
      });
  }

  /** Disconnect WS, POST /end, apply scores + optional unit summary. */
  endConversationAndFeedback(): void {
    if (this.sessionArchiveView()) return;
    if (this.feedbackRequestPending()) return;
    const sid = this._activeSessionId();
    if (sid <= 0) {
      this.errorMessage.set('Session is not ready yet. Wait until the chat has started.');
      this.cdr.markForCheck();
      return;
    }
    if (!this.ws.isOpen()) {
      this.errorMessage.set('Not connected.');
      this.cdr.markForCheck();
      return;
    }
    if (this.pendingTurnSaves() > 0) {
      this.errorMessage.set('Please wait a moment, your latest turn is still being saved.');
      this.cdr.markForCheck();
      return;
    }

    this.feedbackRequestPending.set(true);
    this.ws.expectGracefulSessionShutdown();
    this.ws.disconnect();

    this.api.postSessionEnd(sid).subscribe({
      next: (res) => {
        this.messages.set(
          mergeTurnScoresAndSessionFeedback(
            this.messages(),
            res.turns ?? [],
            res.session_feedback ?? '',
          ),
        );
        this.sessionEndedWithFeedback.set(true);
        if (res.roadmap_unit_completed && sid > 0) this._fetchUnitStepSummary(sid);
        this.feedbackRequestPending.set(false);
        this.cdr.markForCheck();
      },
      error: () => {
        this.feedbackRequestPending.set(false);
        this.errorMessage.set('Could not load session feedback. Try again or use Back.');
        this.cdr.markForCheck();
      },
    });
  }

  onTtsRateChange(rate: string): void {
    this.ttsRate.set(rate);
    this.accountService.patchMe({ tts_rate: rate }).subscribe(NOOP);
    this._sendTtsPreferences(rate, this.ttsVoice());
  }

  onTtsVoiceChange(voiceId: string): void {
    this.ttsVoice.set(voiceId);
    this.accountService.patchMe({ tts_voice: voiceId }).subscribe(NOOP);
    this._sendTtsPreferences(this.ttsRate(), voiceId);
  }

  async previewVoice(voiceId: string): Promise<void> {
    this.previewingVoiceId.set(voiceId);
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

  onLevelChange(level: string | null = ''): void {
    const value = level ?? '';
    this.conversationLevel.set(value);
    if (this.connected()) {
      this.ws.sendJson({ type: WS_TYPE_SET_LEVEL, level: value });
    }
  }

  openGuidePanel(message: ChatMessage, index: number): void {
    this.guidePanelMode.set(GUIDE_PANEL_MODE_GUIDE);
    this.selectedForGuide.set({ index, message });
    this._loadGuideSuggestions(message, index, false);
  }

  private _loadGuideSuggestions(message: ChatMessage, index: number, forceRefresh: boolean): void {
    const question = message.text?.trim() || '';
    if (!question) {
      this.guideSuggestions.set(['No question text.']);
      this.guideLoading.set(false);
      return;
    }
    if (!forceRefresh) {
      const cached = parseGuidelineSections(message.guideline);
      if (cached != null && cached.length > 0) {
        this.guideSuggestions.set(cached);
        this.guideLoading.set(false);
        this.cdr.detectChanges();
        return;
      }
    }
    this.guideSuggestions.set([]);
    this.guideLoading.set(true);
    const prior = priorContextLinesBeforeIndex(this.messages(), index);
    this.api.getGuidance(question, message.turnId, this.conversationLevel(), prior).subscribe({
      next: (res) => {
        const suggestions = res.suggestions || [];
        this.guideSuggestions.set(suggestions);
        if (suggestions.length > 0) {
          this.messages.update((list) => {
            const next = [...list];
            if (next[index]) {
              next[index] = {
                ...next[index],
                guideline: stringifyGuidelineSections(suggestions),
              };
            }
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

  openOptimizePanel(message: ChatMessage, index: number): void {
    this.guidePanelMode.set('optimize');
    this.selectedForGuide.set({ index, message });
    this._loadOptimizeSuggestions(message, index);
  }

  private _loadOptimizeSuggestions(message: ChatMessage, index: number): void {
    const source = message.text?.trim() || '';
    if (!source) {
      this.guideSuggestions.set(['No user message text to optimize.']);
      this.guideLoading.set(false);
      return;
    }
    this.guideSuggestions.set([]);
    this.guideLoading.set(true);
    const prior = priorContextLinesBeforeIndex(this.messages(), index);
    this.api.optimizeUserReply(source, this.conversationLevel(), prior).subscribe({
      next: (res) => {
        this.guideSuggestions.set(res.suggestions || []);
        this.guideLoading.set(false);
        this.cdr.detectChanges();
      },
      error: () => {
        this.guideSuggestions.set(['Could not optimize this message. Try again.']);
        this.guideLoading.set(false);
        this.cdr.detectChanges();
      },
    });
  }

  refreshGuidePanel(): void {
    const sel = this.selectedForGuide();
    if (!sel) return;
    const current = this.messages()[sel.index] ?? sel.message;
    if (this.guidePanelMode() === GUIDE_PANEL_MODE_GUIDE) {
      this._loadGuideSuggestions(current, sel.index, true);
      return;
    }
    this._loadOptimizeSuggestions(current, sel.index);
  }

  closeGuidePanel(): void {
    this._endGuidePanelResize();
    this.selectedForGuide.set(null);
    this.guideSuggestions.set([]);
    this.guideLoading.set(false);
  }

  onGuideResizePointerDown(event: PointerEvent): void {
    if (!this.guidePanelSidebarDesktop()) return;
    event.preventDefault();
    const handle = event.currentTarget as HTMLElement;
    handle.setPointerCapture(event.pointerId);

    const startX = event.clientX;
    const startW = this.guidePanelWidthPx();

    const onMove = (ev: PointerEvent) => {
      const delta = startX - ev.clientX;
      const next = Math.min(GUIDE_PANEL_MAX_W, Math.max(GUIDE_PANEL_MIN_W, startW + delta));
      this.guidePanelWidthPx.set(next);
    };

    const onEnd = (ev: PointerEvent) => {
      handle.releasePointerCapture(ev.pointerId);
      handle.removeEventListener('pointermove', onMove);
      handle.removeEventListener('pointerup', onEnd);
      handle.removeEventListener('pointercancel', onEnd);
      this._guideResizeAbort = null;
      try {
        localStorage.setItem(GUIDE_PANEL_WIDTH_LS, String(this.guidePanelWidthPx()));
      } catch {
        /* ignore */
      }
    };

    this._guideResizeAbort = () => {
      try {
        handle.releasePointerCapture(event.pointerId);
      } catch {
        /* ignore */
      }
      handle.removeEventListener('pointermove', onMove);
      handle.removeEventListener('pointerup', onEnd);
      handle.removeEventListener('pointercancel', onEnd);
    };

    handle.addEventListener('pointermove', onMove);
    handle.addEventListener('pointerup', onEnd);
    handle.addEventListener('pointercancel', onEnd);
  }

  private _endGuidePanelResize(): void {
    this._guideResizeAbort?.();
    this._guideResizeAbort = null;
  }

  private _sendTtsPreferences(rate?: string, voice?: string): void {
    if (!this.connected()) return;
    this.ws.sendJson({
      type: WS_TYPE_TTS_PREFERENCES,
      ttsRate: rate ?? this.ttsRate(),
      ttsVoice: voice ?? this.ttsVoice(),
    });
  }

  async startRecording(): Promise<void> {
    if (this.sessionArchiveView() || this.recording() || !this.canRecord()) return;
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
    this.ws.sendJson({ type: WS_TYPE_AUDIO_END });
  }

  sendText(): void {
    const text = this.chatInput().trim();
    if (!text) return;
    if (!this.connected() || this.messages().length === 0) return;
    if (
      !this.ws.sendJson({
        type: WS_TYPE_USER_TEXT,
        text,
      })
    ) {
      this.errorMessage.set(
        'Không gửi được tin — kết nối WebSocket chưa sẵn sàng hoặc đã ngắt. Đợi “Connecting” xong hoặc tải lại trang.',
      );
      return;
    }
    this.chatInput.set('');
  }

  async playMessageAudio(msg: ChatMessage, index: number, kind: 'user' | 'ai'): Promise<void> {
    if (this.playingMessageIndex() === index) {
      this.audio.stopPlayback();
      this.playingMessageIndex.set(-1);
      this.cdr.detectChanges();
      return;
    }

    const buf = await this._resolveMessagePlaybackBuffer(msg, index, kind);
    if (!buf) return;

    this.audio.stopPlayback();
    this.playingMessageIndex.set(index);
    this.cdr.detectChanges();
    try {
      await this.audio.playAudioBuffer(buf);
    } catch {
      // ignore
    } finally {
      this.playingMessageIndex.set(-1);
      this.cdr.detectChanges();
    }
  }

  /** 0-based learner turn index for the user bubble at `messageIndex`. */
  userTurnIndexAtMessage(messageIndex: number): number {
    const list = this.messages();
    let n = 0;
    for (let i = 0; i < messageIndex && i < list.length; i++) {
      if (list[i].role === CHAT_ROLE_USER) n += 1;
    }
    return n;
  }

  /**
   * While text is still streaming, `lastAiMessageIndex` is only set when partial `done` is true,
   * so it can still point at the *previous* AI turn. Audio may finish first — attach to the
   * in-progress bubble via `pendingAiMsgIndex` instead.
   */
  private _targetAiMessageIndexForAudioAttach(): number {
    return this.pendingAiMsgIndex >= 0 ? this.pendingAiMsgIndex : this.lastAiMessageIndex;
  }

  private _finalizeAssistantAudioPlayback(): void {
    const idx = this._targetAiMessageIndexForAudioAttach();
    this.messages.update((m) => attachConcatenatedAiAudio(m, idx, this.currentAiAudioChunks));
    this.currentAiAudioChunks = [];
    this.lastAiMessageIndex = -1;
    this.audio.endStreamingPlayback().then(() => {
      this.aiSpeaking.set(false);
      this.cdr.detectChanges();
    });
  }

  reworkAllowed(): boolean {
    return (
      !this.sessionArchiveView() &&
      this.connected() &&
      !this.recording() &&
      !this.transcribing() &&
      !this.aiSpeaking() &&
      this.pendingAiMsgIndex === -1
    );
  }

  requestRework(messageIndex: number): void {
    if (this.sessionArchiveView() || !this.reworkAllowed()) return;
    const list = this.messages();
    if (messageIndex < 0 || messageIndex >= list.length) return;
    if (list[messageIndex].role !== CHAT_ROLE_USER) return;
    const turnIndex = this.userTurnIndexAtMessage(messageIndex);
    this.audio.stopPlayback();
    this.playingMessageIndex.set(-1);
    this.ws.sendJson({ type: WS_TYPE_REWORK, turnIndex });
  }

  private _resetConversationStreamingState(): void {
    this.pendingAiMsgIndex = -1;
    this.lastAiMessageIndex = -1;
    this.currentAiAudioChunks = [];
    this.preTextAiAudioChunks = [];
    this.preTextAiAudioEnded = false;
    this.lastUserRecording = null;
    this.playingMessageIndex.set(-1);
    this.aiSpeaking.set(false);
    this.transcribing.set(false);
    this.audio.stopPlayback();
  }

  private _onDeviceLostDuringRecording(): void {
    if (!this.recording()) return;
    this.recording.set(false);
    this.cdr.detectChanges();
    this.audio.stopRecording().then(() => {
      this.ws.sendJson({ type: WS_TYPE_AUDIO_END });
      this.errorMessage.set('');
      this.deviceChangedNotice.set('Microphone changed. You can hold to speak again.');
      this.cdr.detectChanges();
      setTimeout(() => {
        this.deviceChangedNotice.set('');
        this.cdr.detectChanges();
      }, 4000);
    });
  }

  private _activeSessionId(): number {
    return this.liveSessionId() > 0 ? this.liveSessionId() : this.sessionId();
  }

  private _fetchUnitStepSummary(sessionId: number): void {
    this.api.getUnitStepSummary(sessionId).subscribe({
      next: (s: UnitStepSummary) => {
        this.unitCompleteSummary.set(s);
        this.cdr.detectChanges();
      },
      error: () => {
        this.unitCompleteSummary.set(null);
        this.cdr.detectChanges();
      },
    });
  }

  private _applyTopicLevelAndLiveSession(msg: Record<string, unknown>): void {
    const tl = msg['topicLevel'];
    if (typeof tl === 'string' && tl.trim() !== '' && this.conversationLevel() === '') {
      this.conversationLevel.set(tl.trim());
    }
    const sid = msg['sessionId'];
    if (typeof sid === 'number' && Number.isFinite(sid) && sid > 0) {
      this.liveSessionId.set(sid);
      if (msg['message'] === WS_STATUS_SESSION_STARTED && this.sessionId() <= 0) {
        const tid = this.topicId();
        this._skipBootstrapForSessionUrlSync = { topicId: tid, sessionId: sid };
        void this.router.navigate([], {
          relativeTo: this.route,
          queryParams: { sessionId: String(sid) },
          queryParamsHandling: 'merge',
          replaceUrl: true,
        });
      }
    }
  }

  /**
   * Backend sends TTS chunks before text. Buffer playback until the first `assistant_partial`
   * for this turn. After a completed assistant message, `lastAiMessageIndex` is not -1, so
   * never use that alone as the guard — use "last bubble is still the user's line".
   */
  private _assistantAudioShouldWaitForFirstTextChunk(): boolean {
    const last = this.messages().at(-1);
    return last?.role === CHAT_ROLE_USER;
  }

  private _onWsUserTranscript(text: string, userAudio: ArrayBuffer | undefined): void {
    const userMsg: ChatMessage = { role: CHAT_ROLE_USER, text };
    if (userAudio != null) {
      userMsg.userAudio = userAudio;
    } else if (this.lastUserRecording) {
      userMsg.userAudio = this.lastUserRecording;
      this.lastUserRecording = null;
    }
    this.preTextAiAudioChunks = [];
    this.preTextAiAudioEnded = false;
    this.messages.update((m) => [...m, userMsg]);
    this.pendingTurnSaves.update((n) => n + 1);
    this.pendingAiMsgIndex = -1;
    if (this.unitStepMeta()) {
      this.unitStepMeta.update((meta) =>
        meta ? { ...meta, scoredTurnsSoFar: meta.scoredTurnsSoFar + 1 } : null,
      );
    }
  }

  private _onWsAssistantPartial(chunk: string, done: boolean): void {
    const startsNewAiMessage = this.pendingAiMsgIndex === -1;
    if (startsNewAiMessage) {
      this.currentAiAudioChunks = [];
    }
    const out = applyAssistantPartialFrame(
      this.messages(),
      this.pendingAiMsgIndex,
      this.lastAiMessageIndex,
      chunk,
      done,
    );
    this.messages.set(out.messages);
    this.pendingAiMsgIndex = out.pendingAiMsgIndex;
    this.lastAiMessageIndex = out.lastAiMessageIndex;
    if (startsNewAiMessage && this.preTextAiAudioChunks.length > 0) {
      this.currentAiAudioChunks = [...this.preTextAiAudioChunks];
      this.preTextAiAudioChunks = [];
      if (this.ttsEnabled()) {
        this.audio.stopPlayback();
        for (const preChunk of this.currentAiAudioChunks) {
          this.audio.enqueueStreamingChunk(preChunk);
        }
        this.aiSpeaking.set(true);
        this.cdr.detectChanges();
      }
      if (this.preTextAiAudioEnded) {
        this.preTextAiAudioEnded = false;
        this._finalizeAssistantAudioPlayback();
      }
    }
    if (startsNewAiMessage && this.preTextAiAudioEnded && this.preTextAiAudioChunks.length === 0) {
      this.preTextAiAudioEnded = false;
    }
    if (done) {
      // Final status guard: clear speaking state when the assistant text stream is fully delivered.
      this.aiSpeaking.set(false);
    }
  }

  private _onWsAssistantAudioEnd(): void {
    if (this._assistantAudioShouldWaitForFirstTextChunk()) {
      this.preTextAiAudioEnded = true;
      return;
    }
    this._finalizeAssistantAudioPlayback();
  }

  private _onWsAssistantAudioChunk(bytes: ArrayBuffer): void {
    if (this._assistantAudioShouldWaitForFirstTextChunk()) {
      this.preTextAiAudioChunks.push(bytes);
      return;
    }
    this.currentAiAudioChunks.push(bytes);
    if (this.ttsEnabled()) {
      if (this.currentAiAudioChunks.length === 1) this.audio.stopPlayback();
      this.audio.enqueueStreamingChunk(bytes);
      this.aiSpeaking.set(true);
      this.cdr.detectChanges();
    }
  }

  private _onWsSessionScores(turns: SessionScoreTurn[], sessionFeedback: string | undefined): void {
    this.messages.set(mergeTurnScoresAndSessionFeedback(this.messages(), turns, sessionFeedback));
  }

  private _onWsTurnSaved(
    assistantMessageId: number,
    userMessageId: number,
    hasUserAudio: boolean,
    indexInSession: number,
  ): void {
    this.pendingTurnSaves.update((n) => (n > 0 ? n - 1 : 0));
    this.messages.update((list) => {
      const { next, persistGuideline } = mergeTurnSavedIntoMessages(
        list,
        assistantMessageId,
        userMessageId,
        hasUserAudio,
        indexInSession,
      );
      if (persistGuideline) {
        this.api
          .patchMessageGuideline(persistGuideline.messageId, persistGuideline.guideline)
          .subscribe({ error: () => {} });
      }
      return next;
    });
  }

  private _applyAccountTtsToSignals(me: {
    tts_voice?: string | null;
    tts_rate?: string | null;
  }): void {
    const voice = me.tts_voice;
    const rate = me.tts_rate;
    if (voice != null && String(voice).trim() !== '') this.ttsVoice.set(String(voice));
    if (rate != null && String(rate).trim() !== '') this.ttsRate.set(String(rate));
  }

  private _reportMessageAudioLoadFailed(): void {
    this.errorMessage.set('Could not load audio for this message.');
    this.cdr.markForCheck();
  }

  private async _fetchMessageAudioFromApi(
    turnId: number,
    apiKind: 'user' | 'assistant',
  ): Promise<ArrayBuffer | null> {
    try {
      return await firstValueFrom(this.api.getMessageAudio(turnId, apiKind));
    } catch {
      this._reportMessageAudioLoadFailed();
      return null;
    }
  }

  private async _fetchOpeningLineAudio(sessionId: number): Promise<ArrayBuffer | null> {
    try {
      return await firstValueFrom(this.api.getSessionOpeningAudio(sessionId));
    } catch {
      this._reportMessageAudioLoadFailed();
      return null;
    }
  }

  private async _bufferFromMessageTurn(
    msg: ChatMessage,
    index: number,
    kind: 'user' | 'ai',
  ): Promise<ArrayBuffer | null> {
    if (msg.turnId == null) return null;
    const canFetchUser = kind === CHAT_ROLE_USER && msg.hasUserRecording;
    const canFetchAi = kind === CHAT_ROLE_AI && msg.hasAiAudio;
    if (!canFetchUser && !canFetchAi) return null;
    const apiKind = kind === CHAT_ROLE_USER ? API_AUDIO_KIND_USER : API_AUDIO_KIND_ASSISTANT;
    const buf = await this._fetchMessageAudioFromApi(msg.turnId, apiKind);
    if (!buf) return null;
    this._patchMessageCachedAudio(index, kind, buf);
    return buf;
  }

  private async _bufferFromOpeningLine(
    msg: ChatMessage,
    index: number,
  ): Promise<ArrayBuffer | null> {
    if (!msg.isOpeningLine || !msg.hasAiAudio) return null;
    const sid = this._activeSessionId();
    if (sid <= 0) return null;
    const buf = await this._fetchOpeningLineAudio(sid);
    if (!buf) return null;
    this._patchMessageCachedAudio(index, CHAT_ROLE_AI, buf);
    return buf;
  }

  private async _resolveMessagePlaybackBuffer(
    msg: ChatMessage,
    index: number,
    kind: 'user' | 'ai',
  ): Promise<ArrayBuffer | null> {
    const embedded = kind === CHAT_ROLE_USER ? msg.userAudio : msg.aiAudio;
    if (embedded) return embedded;
    if (msg.turnId != null) {
      return this._bufferFromMessageTurn(msg, index, kind);
    }
    if (kind === CHAT_ROLE_AI) {
      return this._bufferFromOpeningLine(msg, index);
    }
    return null;
  }

  private _patchMessageCachedAudio(index: number, kind: 'user' | 'ai', buf: ArrayBuffer): void {
    this.messages.update((list) => {
      const next = [...list];
      const cur = next[index];
      if (!cur) return list;
      next[index] = kind === CHAT_ROLE_USER ? { ...cur, userAudio: buf } : { ...cur, aiAudio: buf };
      return next;
    });
  }

  private _handleMessage(msg: Record<string, unknown> & { type: string }): void {
    routeConversationWsMessage(msg, this._wsSink);
  }

  closeUnitCompleteModal(): void {
    this.unitCompleteSummary.set(null);
    this.cdr.detectChanges();
  }

  goToRoadmapAfterUnit(): void {
    const s = this.unitCompleteSummary();
    const tid = s?.topic_id ?? this.topicId();
    this.unitCompleteSummary.set(null);
    void this.router.navigate(['/topics', tid, 'roadmap']);
  }

  private _scheduleDetectChanges(msg: WsMessage): void {
    if (msg['type'] === WS_TYPE_ASSISTANT_PARTIAL) {
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

  scrollToBottom(): void {
    this.messageList()?.scrollToBottom();
  }
}
