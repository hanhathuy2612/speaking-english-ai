// Shapes of the backend API and WebSocket protocol (docs/architecture.md).

export type Speech = {
  words: number;
  wpm: number | null;
  wpm_speaking: number | null;
  long_pauses: number;
  low_conf: string[];
};

export type UnclearReason = "not_english" | "low_confidence";

export type UnitSummary = { id: string; title: string };

export type UnitInfo = {
  id: string;
  title: string;
  goal: string;
  scenario: string;
  phrases: { say: string }[];
  stt: string;
};

export type CompareItem =
  | { kind: "word"; text: string; status: "ok" | "wrong" | "miss"; heard?: string | null }
  | { kind: "extra"; text: string };

export type ShadowResult = {
  target: string;
  heard: string;
  compare: { items: CompareItem[]; correct: number; total: number; accuracy: number };
  speech: Speech;
  original: Speech | null;
};

export type SessionSummary = {
  turns: number;
  questions: number;
  phrases_used: string[];
  phrases_missed: string[];
  wpm: number | null;
  wpm_speaking: number | null;
  long_pauses: number;
  spoken_turns: number;
};

export type Metrics = {
  stt_ms?: number;
  llm_first_ms?: number;
  first_audio_ms?: number;
  total_ms?: number;
};

export type ServerMessage =
  | { type: "started"; unit: UnitInfo }
  | { type: "status"; msg: "transcribing" | "thinking" }
  | { type: "transcript"; text: string; speech: Speech; used: number[]; unclear: boolean; reason: UnclearReason | null; conf: number | null }
  | { type: "sentence"; text: string; role: "ai" | "model" }
  | { type: "note"; text: string; retry: boolean }
  | ({ type: "shadow_result" } & ShadowResult)
  | ({ type: "metrics" } & Metrics)
  | { type: "progress"; q: number; n: number; done: boolean }
  | ({ type: "summary" } & SessionSummary)
  | { type: "undone"; used: number[] }
  | { type: "turn_done"; can_undo?: boolean }
  | { type: "error"; msg: string };

export type ClientMessage =
  | { type: "start"; unit: string }
  | { type: "text"; text: string }
  | { type: "undo" }
  | { type: "shadow"; text: string }
  | { type: "say_it"; text: string };

export type HistorySession = {
  id: number;
  unit_id: string;
  unit_title: string;
  started_at: string;
  completed: boolean;
  turns: number;
  spoken_turns: number;
  unclear_turns: number;
  words: number;
  wpm: number | null;
  wpm_speaking: number | null;
  long_pauses: number;
  pauses_per_100_words: number | null;
  phrases_used: number;
  phrase_total: number;
  shadow_attempts: number;
  shadow_accuracy: number | null; // % of reference words read correctly, all attempts pooled
};

export type BenchItem = { text: string; done: boolean };
