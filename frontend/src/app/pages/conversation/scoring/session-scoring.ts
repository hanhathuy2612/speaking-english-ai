import { CHAT_ROLE_AI, CHAT_ROLE_USER } from '../model/chat-roles';
import type { ChatMessage, SessionScoreTurn } from '../model/models';

export function mergeTurnScoresAndSessionFeedback(
  messages: ChatMessage[],
  turns: SessionScoreTurn[],
  sessionFeedback: string | undefined,
): ChatMessage[] {
  const rawFb = (sessionFeedback ?? '').trim();
  let list = messages.filter((m) => !m.sessionRecap);

  let ti = 0;
  for (let i = 0; i < list.length && ti < turns.length; i++) {
    if (list[i].role !== CHAT_ROLE_USER) continue;
    if (i + 1 >= list.length || list[i + 1].role !== CHAT_ROLE_AI) continue;
    const sc = turns[ti++];
    // sc.turnId is the assistant message id; only the AI bubble should use it for API calls.
    list[i + 1] = { ...list[i + 1], turnId: sc.turnId };
  }

  if (rawFb) {
    list = [...list, { role: CHAT_ROLE_AI, text: rawFb, sessionRecap: true }];
  }

  return list;
}
