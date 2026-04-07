import type { ChatMessage } from '../model/models';

export interface WsHistoryRow {
  role: string;
  text: string;
  turnId?: number;
  guideline?: string;
  hasUserAudio?: boolean;
  hasAssistantAudio?: boolean;
  isOpening?: boolean;
}

export function mapWsHistoryToChatMessages(rows: WsHistoryRow[]): ChatMessage[] {
  return rows.map((m) => {
    if (m.role === 'user') {
      return {
        role: 'user' as const,
        text: m.text,
        turnId: m.turnId,
        ...(m.hasUserAudio ? { hasUserRecording: true } : {}),
      };
    }
    return {
      role: 'ai' as const,
      text: m.text,
      turnId: m.turnId,
      guideline: m.guideline ?? undefined,
      ...(m.hasAssistantAudio ? { hasAiAudio: true } : {}),
      ...(m.isOpening ? { isOpeningLine: true } : {}),
    };
  });
}
