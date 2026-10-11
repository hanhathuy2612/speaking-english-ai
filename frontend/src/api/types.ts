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

export type Topic = {
  id: string;
  title: string;
  description: string;
  locked: boolean; // its stage is not open yet (docs/features/roadmap.md)
  units: UnitStatus[];
};

/** GET /api/units: `next_unit` is the first unit not completed in the open stages. */
export type UnitsResponse = { topics: Topic[]; next_unit: string | null };

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
  | {
      kind: "word";
      text: string;
      status: "ok" | "wrong" | "miss";
      heard?: string | null;
    }
  | { kind: "extra"; text: string };

export type ShadowResult = {
  target: string;
  heard: string;
  compare: {
    items: CompareItem[];
    correct: number;
    total: number;
    accuracy: number;
  };
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
  session_id: number | null; // history row, for the end-of-session review
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
  | {
      type: "transcript";
      text: string;
      speech: Speech;
      used: number[];
      unclear: boolean;
      reason: UnclearReason | null;
      conf: number | null;
    }
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
  targets: {
    seconds: number;
    wpm_speaking: number;
    hesitations_per_100: number;
  };
  checks: CheckRow[];
};

// ----- Pronunciation drills (docs/features/pronunciation-drills.md) -----

export type DrillSentence = { id: string; text: string; focus: string[] };

/** Recent focus-word accuracy: last `window` attempts, accuracy in % (null before any attempt). */
export type FocusAccuracy = { attempts: number; accuracy: number | null };

export type DrillSet = FocusAccuracy & {
  id: string; // "mine" = sentences you misread before
  title: string;
  measured: string; // the mistake measured on your voice that this set targets
  tip: string;
  sentences: DrillSentence[];
};

export type DrillState = {
  enabled: boolean;
  window: number;
  recent: FocusAccuracy;
  sets: DrillSet[];
};

export type DrillResult = {
  target: string;
  heard: string;
  items: (CompareItem & { focus?: boolean })[];
  correct: number;
  total: number;
  accuracy: number;
  focus_correct: number;
  focus_total: number;
};

// ----- 4/3/2 fluency exercise (docs/features/fluency-432.md) -----

export type FluencyRound = {
  round: number;
  limit_s: number;
  text: string;
  words: number;
  duration_s: number;
  wpm_speaking: number | null; // null when less than 30 s of English
  hesitations_per_100: number | null;
  not_english: boolean;
};

export type FluencyResult = FluencyRound & { run: string; measurable: boolean };

export type FluencyRun = {
  run: string;
  prompt_id: string;
  prompt: string;
  created_at: string;
  rounds: FluencyRound[];
  complete: boolean;
};

export type FluencyState = {
  enabled: boolean;
  prompt: CheckPrompt;
  rounds: number[];
  runs: FluencyRun[];
};

// ----- Roadmap stages (docs/features/roadmap.md) -----

export type CheckLevel = {
  seconds: number;
  wpm_speaking?: number;
  hesitations_per_100?: number;
};

export type Requirement =
  | {
      kind: "units" | "drill_sets" | "fluency_runs";
      done: number;
      total: number;
      met: boolean;
    }
  | ({
      kind: "drill_accuracy";
      target: number;
      window: number;
      met: boolean;
    } & FocusAccuracy)
  | {
      kind: "check";
      target: CheckLevel;
      // the check that met the level, otherwise the latest one
      latest: {
        created_at: string;
        duration_s: number;
        wpm_speaking: number | null;
        hesitations_per_100: number | null;
      } | null;
      met: boolean;
    };

export type StageStatus = "passed" | "current" | "locked";

export type Stage = {
  id: string;
  title: string;
  goal: string;
  practice?: "drills" | "fluency";
  topics: Topic[];
  requirements: Requirement[];
  status: StageStatus;
};

// ----- Review cards (docs/features/review.md) -----

export type ReviewCard = {
  id: number;
  kind: "note" | "phrase";
  unit_id: string;
  unit_title: string;
  question: string;
  said: string | null; // note cards: what you said back then
  target: string; // the NOTE, or the phrase to use
  box: number; // Leitner box, 0 = new or forgotten
  due: string; // YYYY-MM-DD
  reviews: number;
  session_id: number | null;
};

export type ReviewStats = {
  due: number;
  active: number;
  learned: number; // box >= 4
  reviews: number; // last 30 days
  good: number;
  recall: number | null; // % graded "remembered", last 30 days
};

export type ReviewState = { enabled: boolean; stats: ReviewStats; cards: ReviewCard[] };

export type ReviewAttempt = {
  heard: string;
  suggest: "good" | "again";
  phrase_used?: boolean; // phrase cards
  items?: CompareItem[]; // note cards: the NOTE word by word against what you said
  correct?: number;
  total?: number;
  accuracy?: number;
};
