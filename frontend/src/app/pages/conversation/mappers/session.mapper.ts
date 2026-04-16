import type { SessionDetailTurn } from '@/services/api.service';
import { decodeEscapedLineBreaks } from '../../../shared/utils/chat-text';
import { CHAT_ROLE_AI, CHAT_ROLE_USER } from '../model/chat-roles';
import type { ChatMessage } from '../model/models';

/** Build chat transcript from GET /conversation/sessions/{id} (ended or in-progress). */
export function mapSessionDetailTurnsToMessages(
  turns: SessionDetailTurn[],
  openingMessage?: string | null,
  openingHasAudio?: boolean,
  sessionFeedback?: string | null,
): ChatMessage[] {
  const out: ChatMessage[] = [];
  const open = typeof openingMessage === 'string' ? openingMessage.trim() : '';
  if (open) {
    out.push({
      role: CHAT_ROLE_AI,
      text: decodeEscapedLineBreaks(open),
      isOpeningLine: true,
      ...(openingHasAudio ? { hasAiAudio: true } : {}),
    });
  }
  for (const t of turns) {
    out.push({
      role: CHAT_ROLE_USER,
      text: decodeEscapedLineBreaks(t.user_text),
      turnId: t.user_message_id,
      ...(t.has_user_audio ? { hasUserRecording: true } : {}),
    }, {
      role: CHAT_ROLE_AI,
      text: decodeEscapedLineBreaks(t.assistant_text),
      turnId: t.turn_id,
      ...(t.has_assistant_audio ? { hasAiAudio: true } : {}),
      ...(t.guideline ? { guideline: t.guideline } : {}),
    });
  }
  const recap = typeof sessionFeedback === 'string' ? sessionFeedback.trim() : '';
  if (recap) {
    out.push({
      role: CHAT_ROLE_AI,
      text: decodeEscapedLineBreaks(recap),
      sessionRecap: true,
    });
  }
  return out;
}
