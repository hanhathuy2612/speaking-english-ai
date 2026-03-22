export interface ChatMessage {
  role: 'user' | 'ai';
  text: string;
  partial?: boolean;
  userAudio?: ArrayBuffer;
  aiAudio?: ArrayBuffer;
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
