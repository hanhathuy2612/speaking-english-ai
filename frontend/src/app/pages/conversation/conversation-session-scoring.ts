import type { ChatMessage, SessionScoreTurn } from './conversation.models';

export function mergeTurnScoresAndSessionFeedback(
  messages: ChatMessage[],
  turns: SessionScoreTurn[],
  sessionFeedback: string | undefined,
): ChatMessage[] {
  const rawFb = (sessionFeedback ?? '').trim();
  let list = messages.filter((m) => !m.sessionRecap);

  let ti = 0;
  for (let i = 0; i < list.length && ti < turns.length; i++) {
    if (list[i].role !== 'user') continue;
    const sc = turns[ti++];
    list[i] = { ...list[i], turnId: sc.turnId };
    if (i + 1 < list.length && list[i + 1].role === 'ai') {
      list[i + 1] = { ...list[i + 1], turnId: sc.turnId };
    }
  }

  if (rawFb) {
    list = [...list, { role: 'ai', text: rawFb, sessionRecap: true }];
  }

  return list;
}
