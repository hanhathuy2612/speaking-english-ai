/** Mirrors backend `app/schemas/learning_pack.py` (subset used by FE). */

export interface LearningPackVocabItem {
  term: string;
  meaning: string;
  collocations: string[];
  example: string | null;
}

export interface LearningPackPatternItem {
  pattern: string;
  usage: string;
  example: string;
}

export interface LearningPackMistakeItem {
  mistake: string;
  fix: string;
  note: string | null;
}

export interface LearningPackModelResponseItem {
  level: string | null;
  text: string;
}

export interface LearningPackIn {
  vocabulary: LearningPackVocabItem[];
  sentence_patterns: LearningPackPatternItem[];
  idea_prompts: string[];
  common_mistakes: LearningPackMistakeItem[];
  model_responses: LearningPackModelResponseItem[];
  tips: string[];
}

export interface LearningPackOut extends LearningPackIn {
  /** unit | topic | fallback — set when resolved for learners */
  source?: string | null;
}

export function emptyLearningPack(): LearningPackIn {
  return {
    vocabulary: [],
    sentence_patterns: [],
    idea_prompts: [],
    common_mistakes: [],
    model_responses: [],
    tips: [],
  };
}

export function learningPackInFromOut(out: LearningPackOut): LearningPackIn {
  return {
    vocabulary: out.vocabulary ?? [],
    sentence_patterns: out.sentence_patterns ?? [],
    idea_prompts: out.idea_prompts ?? [],
    common_mistakes: out.common_mistakes ?? [],
    model_responses: out.model_responses ?? [],
    tips: out.tips ?? [],
  };
}

export function isLearningPackEmpty(pack: LearningPackIn | LearningPackOut | null): boolean {
  if (!pack) return true;
  return (
    (pack.vocabulary?.length ?? 0) === 0 &&
    (pack.sentence_patterns?.length ?? 0) === 0 &&
    (pack.idea_prompts?.length ?? 0) === 0 &&
    (pack.common_mistakes?.length ?? 0) === 0 &&
    (pack.model_responses?.length ?? 0) === 0 &&
    (pack.tips?.length ?? 0) === 0
  );
}
