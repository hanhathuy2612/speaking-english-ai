import { CHAT_ROLE_AI, CHAT_ROLE_USER } from '../model/chat-roles';
import type { ChatMessage } from '../model/models';

export interface TurnSavedMergeResult {
  next: ChatMessage[];
  /** Persist locally edited guideline to the server once IDs exist. */
  persistGuideline: { messageId: number; guideline: string } | null;
}

/** Map `turn_saved` WS payload onto in-memory transcript indices (opening line shifts user/ai pairs). */
export function mergeTurnSavedIntoMessages(
  list: ChatMessage[],
  assistantMessageId: number,
  userMessageId: number,
  hasUserAudio: boolean,
  indexInSession: number,
): TurnSavedMergeResult {
  const hasOpening = list.length > 0 && list[0].isOpeningLine === true;
  const offset = hasOpening ? 1 : 0;
  const userIdx = offset + indexInSession * 2;
  const aiIdx = userIdx + 1;
  if (userIdx < 0 || aiIdx >= list.length) {
    return { next: list, persistGuideline: null };
  }

  const next = [...list];
  if (next[userIdx]?.role === CHAT_ROLE_USER) {
    next[userIdx] = {
      ...next[userIdx],
      turnId: userMessageId,
      ...(hasUserAudio ? { hasUserRecording: true } : {}),
    };
  }

  const ai = next[aiIdx];
  let persistGuideline: TurnSavedMergeResult['persistGuideline'] = null;
  if (ai?.role === CHAT_ROLE_AI && !ai.isOpeningLine) {
    next[aiIdx] = { ...ai, turnId: assistantMessageId };
    const g = ai.guideline;
    if (g != null && String(g).trim() !== '') {
      persistGuideline = { messageId: assistantMessageId, guideline: g };
    }
  }

  return { next, persistGuideline };
}
