export interface ChatMessage {
  role: 'user' | 'ai';
  text: string;
  partial?: boolean;
  userAudio?: ArrayBuffer;
  aiAudio?: ArrayBuffer;
  /** Stored recording exists server-side (fetch on play after reload / history). */
  hasUserRecording?: boolean;
  /** Stored TTS exists server-side. */
  hasAiAudio?: boolean;
  /** First assistant line (opening greeting), not a Turn — use session opening-audio API. */
  isOpeningLine?: boolean;
  turnId?: number;
  guideline?: string;
  sessionRecap?: boolean;
}

/** Roadmap step meta from WebSocket (camelCase). */
export interface TopicUnitWsMeta {
  id: number;
  title: string;
  objective: string;
  minTurnsToComplete: number | null;
  minAvgOverall: number | null;
  maxScoredTurns: number | null;
  scoredTurnsSoFar: number;
}

export interface SessionScoreTurn {
  turnId: number;
  fluency: number;
  vocabulary: number;
  grammar: number;
  overall: number;
  feedback: string;
}
