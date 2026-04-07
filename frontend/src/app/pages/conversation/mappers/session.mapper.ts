import type { SessionDetailTurn } from '@/services/api.service';
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
      role: 'ai',
      text: open,
      isOpeningLine: true,
      ...(openingHasAudio ? { hasAiAudio: true } : {}),
    });
  }
  for (const t of turns) {
    out.push({
      role: 'user',
      text: t.user_text,
      turnId: t.user_message_id,
      ...(t.has_user_audio ? { hasUserRecording: true } : {}),
    });
    out.push({
      role: 'ai',
      text: t.assistant_text,
      turnId: t.turn_id,
      ...(t.has_assistant_audio ? { hasAiAudio: true } : {}),
      ...(t.guideline ? { guideline: t.guideline } : {}),
    });
  }
  const recap = typeof sessionFeedback === 'string' ? sessionFeedback.trim() : '';
  if (recap) {
    out.push({
      role: 'ai',
      text: recap,
      sessionRecap: true,
    });
  }
  return out;
}
