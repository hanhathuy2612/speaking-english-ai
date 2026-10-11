// Shapes of the backend API and WebSocket protocol (docs/architecture.md).

export type Speech = {
  words: number;
  wpm: number | null;
  wpm_speaking: number | null;
  long_pauses: number;
  low_conf: string[];
};

export type UnclearReason = "not_english" | "low_confidence";

/** One unit on the roadmap, with practice status from the history store. */
export type UnitStatus = {
  id: string;
  title: string;
  goal: string;
  questions: number;
  sessions: number; // sessions with at least one answer
  completed: number; // sessions that reached the last question
  last_at: string | null;
};

export type Topic = { id: string; title: string; description: string; units: UnitStatus[] };

export type UnitInfo = {
  id: string;
  title: string;
  goal: string;
  scenario: string;
  phrases: { say: string }[];
  stt: string;
  partner: string; // who the AI plays, e.g. "Người phỏng vấn", "Đồng nghiệp"
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

// ----- Speaking check (docs/features/speaking-check.md) -----

export type CheckPrompt = { id: string; text: string; hint: string };

export type CheckCriterion = {
  key: "duration" | "wpm_speaking" | "hesitations_per_100" | "english";
  label: string;
  value: number | boolean | null;
  target: number | boolean;
  passed: boolean;
};

export type CheckReport = {
  prompt: CheckPrompt;
  text: string;
  words: number;
  duration_s: number;
  wpm: number | null;
  wpm_speaking: number | null;
  hesitations: number; // pauses > 0.7 s inside a sentence
  hesitations_per_100: number | null;
  not_english: boolean;
  measurable: boolean; // at least 30 s of English, so speed and hesitation are judged
  criteria: CheckCriterion[];
  passed: number;
};

export type CheckRow = {
  id: number;
  created_at: string;
  prompt_id: string;
  prompt: string;
  text: string;
  words: number;
  duration_s: number;
  wpm_speaking: number | null;
  hesitations_per_100: number | null;
  not_english: boolean;
  passed: number;
  total: number;
};

export type CheckState = {
  enabled: boolean;
  prompt: CheckPrompt;
  targets: { seconds: number; wpm_speaking: number; hesitations_per_100: number };
  checks: CheckRow[];
};
