import type { WsHistoryRow } from './conversation-history.mapper';
import { mapWsHistoryToChatMessages } from './conversation-history.mapper';
import { handleWsStatusPayload, type StatusRouter } from './conversation-ws-status';
import type { SessionScoreTurn } from './conversation.models';

const MAX_UNIT_TURNS_MSG =
  'You reached the maximum practice turns for this step in this session. Open the roadmap to continue or start again later.';

export interface ConversationWsSink {
  /** status */
  statusRouter: StatusRouter;
  /** history */
  resetStreamingState(): void;
  setMessages(messages: ReturnType<typeof mapWsHistoryToChatMessages>): void;
  /** error */
  setTranscribing(v: boolean): void;
  setErrorMessage(msg: string): void;
  /** user_transcript */
  onUserTranscript(text: string, userAudio: ArrayBuffer | undefined): void;
  /** assistant_partial */
  onAssistantPartial(chunk: string, done: boolean): void;
  /** assistant_audio_end */
  onAssistantAudioEnd(): void;
  /** assistant_audio_chunk */
  onAssistantAudioChunk(bytes: ArrayBuffer): void;
  /** session_scores */
  onSessionScores(turns: SessionScoreTurn[], sessionFeedback: string | undefined): void;
  /** turn_saved — assistantMessageId for AI bubble; userMessageId for user bubble (recordings). */
  onTurnSaved(
    assistantMessageId: number,
    userMessageId: number,
    hasUserAudio: boolean,
    indexInSession: number,
  ): void;
}

export function routeConversationWsMessage(
  msg: Record<string, unknown> & { type: string },
  sink: ConversationWsSink,
): void {
  switch (msg['type']) {
    case 'status':
      handleWsStatusPayload(msg, sink.statusRouter);
      break;
    case 'history': {
      const list = (msg['messages'] as WsHistoryRow[]) ?? [];
      sink.resetStreamingState();
      sink.setMessages(mapWsHistoryToChatMessages(list));
      break;
    }
    case 'error':
      sink.setTranscribing(false);
      {
        const code = msg['message'] as string;
        sink.setErrorMessage(
          code === 'max_unit_turns_reached' ? MAX_UNIT_TURNS_MSG : code || 'Something went wrong',
        );
      }
      break;
    case 'user_transcript':
      sink.setTranscribing(false);
      sink.onUserTranscript(msg['text'] as string, undefined);
      break;
    case 'assistant_partial':
      sink.onAssistantPartial(msg['text'] as string, msg['done'] as boolean);
      break;
    case 'assistant_audio_end':
      sink.onAssistantAudioEnd();
      break;
    case 'assistant_audio_chunk': {
      const b64 = msg['data'] as string;
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)).buffer;
      sink.onAssistantAudioChunk(bytes);
      break;
    }
    case 'session_scores':
      sink.onSessionScores(
        (msg['turns'] as SessionScoreTurn[]) ?? [],
        typeof msg['session_feedback'] === 'string' ? msg['session_feedback'] : undefined,
      );
      break;
    case 'turn_saved': {
      const assistantId = msg['turnId'];
      const userId = msg['userMessageId'];
      const idx = msg['indexInSession'];
      const hasUserAudio = msg['hasUserAudio'] === true;
      if (
        typeof assistantId === 'number' &&
        Number.isFinite(assistantId) &&
        typeof idx === 'number' &&
        Number.isFinite(idx)
      ) {
        const uid = typeof userId === 'number' && Number.isFinite(userId) ? userId : assistantId;
        sink.onTurnSaved(assistantId, uid, hasUserAudio, idx);
      }
      break;
    }
    default:
      break;
  }
}
