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
  lesson: boolean; // has a lesson part before the role-play (docs/features/lesson.md)
  lesson_done: number; // times the lesson part was finished
  done: boolean; // completed, and the lesson finished if there is one
};

export type Topic = {
  id: string;
  title: string;
  description: string;
  locked: boolean; // its stage is not open yet (docs/features/roadmap.md)
  units: UnitStatus[];
};

/** GET /api/units: `next_unit` is the first unit not done in the open stages. */
export type UnitsResponse = { topics: Topic[]; next_unit: string | null };

export type UnitInfo = {
  id: string;
  title: string;
  goal: string;
  scenario: string;
  phrases: { say: string }[];
  stt: string;
  partner: string; // who the AI plays, e.g. "Người phỏng vấn", "Đồng nghiệp"
  lesson: boolean; // the unit has a lesson part (/lesson/:id)
};

// ----- Lesson part of a unit (docs/features/lesson.md) -----

/** A teacher line: English is spoken, Vietnamese is shown on demand ("Dịch"). */
export type LessonLine = { en: string; vi: string };

export type LessonData = {
  id: string;
  title: string;
  goal: string;
  partner: string;
  vocab: { word: string; vi: string }[];
  sentences: { say: string; use: string; use_vi: string }[];
  lines: Record<string, LessonLine>; // keys: intro, vocab, read, good, retry, move_on, outro, s<i>, say<i>, w<i>
  finished: number; // times the lesson part was finished
};

export type LessonReading = {
  target: string;
  heard: string;
  compare: ShadowResult["compare"];
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

/** One step towards a longer answer, shown under the NOTE (docs/features/answer-steps.md). */
export type AnswerStep = { hint: string; say: string; done: boolean };

export type RetellResult = {
  heard: string;
  speech: Speech;
  original: Speech | null; // the first answer to the same question (null if it was typed)
  original_words: number;
  steps: AnswerStep[];
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
  | { type: "note"; text: string; retry: boolean; steps: AnswerStep[] }
  | ({ type: "shadow_result" } & ShadowResult)
  | ({ type: "retell_result" } & RetellResult)
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
  | { type: "retell" }
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
  /** Best reading of each sentence so far, by sentence id (pronunciation-drills.md). */
  best: Record<string, DrillBest>;
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

/** The best reading of a sentence: its result, when, how many readings, and its recording if kept. */
export type DrillBest = DrillResult & { created_at: string; attempts: number; audio_url: string | null };

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

/** One turn of a past session (GET /api/history/sessions/{id}/turns). */
export type HistoryTurn = {
  id: number;
  created_at: string;
  question: string;
  answer: string;
  source: "voice" | "text";
  unclear: number; // 1 = not sent to the AI (not English, or unclear audio)
  note: string | null;
  words: number | null;
  wpm_speaking: number | null;
  audio_url: string | null; // the kept recording, when SAVE_AUDIO_DIR is set
};

// ----- Accounts (docs/features/accounts.md) -----

export type Role = "user" | "admin";

export type User = {
  id: number;
  email: string;
  name: string;
  role: Role;
  verified: boolean;
  disabled: boolean;
  created_at: string;
};

// ----- Content editing for admins (docs/features/content-admin.md) -----

/** A unit as stored (data/units.json schema, docs/features/interview-flow.md). */
export type UnitData = {
  id: string;
  topic: string;
  title: string;
  role?: string; // conversation units: who the AI plays
  partner?: string;
  scenario: string;
  goal: string;
  greeting: string;
  closing: string;
  vocab?: string;
  followups?: number;
  phrases: { say: string; match: string[]; when?: string[] }[];
  questions: { ask: string; simple: string; phrases: number[]; steps: { hint: string; say: string }[] }[];
  lesson?: {
    intro: string;
    intro_vi: string;
    vocab: { word: string; vi: string }[];
    sentences: { phrase: number; say: string; use: string; use_vi: string }[];
  };
};

export type ContentTopic = { id: string; title: string; description: string };

export type ContentUnitRow = {
  id: string;
  topic: string;
  title: string;
  questions: number;
  lesson: boolean;
  source: "file" | "admin"; // admin: edited on the web, no longer follows units.json
  deleted: boolean;
  invalid: boolean; // fails a newer content rule: left out of the app until fixed
  updated_at: string | null;
  updated_by: string | null;
};

export type ContentList = {
  topics: ContentTopic[];
  stages: { id: string; title: string; topics: string[] }[];
  units: ContentUnitRow[];
};
