import type { ChatMessage } from './conversation.models';

/** Apply one assistant_partial WebSocket frame; returns new messages + streaming indices. */
export function applyAssistantPartialFrame(
  messages: ChatMessage[],
  pendingAiMsgIndex: number,
  lastAiMessageIndex: number,
  chunk: string,
  done: boolean,
): {
  messages: ChatMessage[];
  pendingAiMsgIndex: number;
  lastAiMessageIndex: number;
} {
  if (pendingAiMsgIndex === -1) {
    const next = [...messages, { role: 'ai' as const, text: chunk, partial: true }];
    let p = messages.length;
    let l = lastAiMessageIndex;
    if (done) {
      next[p] = { ...next[p], partial: false };
      l = p;
      p = -1;
    }
    return { messages: next, pendingAiMsgIndex: p, lastAiMessageIndex: l };
  }

  const next = [...messages];
  const idx = pendingAiMsgIndex;
  next[idx] = { ...next[idx], text: next[idx].text + chunk };

  if (!done) {
    return { messages: next, pendingAiMsgIndex, lastAiMessageIndex };
  }

  next[idx] = { ...next[idx], partial: false };
  return { messages: next, pendingAiMsgIndex: -1, lastAiMessageIndex: idx };
}

export function attachConcatenatedAiAudio(
  messages: ChatMessage[],
  messageIndex: number,
  chunks: ArrayBuffer[],
): ChatMessage[] {
  if (messageIndex < 0 || chunks.length === 0) return messages;
  const total = chunks.reduce((s, c) => s + c.byteLength, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const c of chunks) {
    out.set(new Uint8Array(c), offset);
    offset += c.byteLength;
  }
  const next = [...messages];
  next[messageIndex] = { ...next[messageIndex], aiAudio: out.buffer };
  return next;
}
