import type { TopicUnitWsMeta } from '../model/models';

export interface ConversationWsStartPayload {
  type: 'start';
  topicId: number;
  ttsRate: string;
  ttsVoice: string;
  /**
   * IELTS band override from the chat header. Omit entirely to use the topic's stored default
   * (server loads `topics.level` — the model never sees this JSON, only the built system prompt).
   */
  level?: string;
  sessionId?: number;
  unitId?: number;
}

export function topicUnitFromWsPayload(raw: unknown): TopicUnitWsMeta | null {
  if (raw == null || typeof raw !== 'object') return null;
  const tu = raw as Record<string, unknown>;
  if (typeof tu['id'] !== 'number') return null;
  return {
    id: tu['id'],
    title: String(tu['title'] ?? ''),
    objective: String(tu['objective'] ?? ''),
    minTurnsToComplete: (tu['minTurnsToComplete'] as number | null) ?? null,
    minAvgOverall: (tu['minAvgOverall'] as number | null) ?? null,
    maxScoredTurns: (tu['maxScoredTurns'] as number | null) ?? null,
    scoredTurnsSoFar: Number(tu['scoredTurnsSoFar'] ?? 0) || 0,
  };
}
