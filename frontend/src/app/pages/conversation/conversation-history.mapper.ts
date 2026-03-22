import type { ChatMessage } from './conversation.models';

export interface WsHistoryRow {
  role: string;
  text: string;
  turnId?: number;
  guideline?: string;
}

export function mapWsHistoryToChatMessages(rows: WsHistoryRow[]): ChatMessage[] {
  return rows.map((m) => ({
    role: m.role === 'user' ? 'user' : 'ai',
    text: m.text,
    ...(m.role === 'assistant' && {
      turnId: m.turnId,
      guideline: m.guideline ?? undefined,
    }),
  }));
}
