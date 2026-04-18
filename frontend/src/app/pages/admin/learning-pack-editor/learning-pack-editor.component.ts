import { CommonModule } from '@angular/common';
import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { finalize } from 'rxjs';
import { ApiService } from '@/shared/services/api.service';
import {
  emptyLearningPack,
  learningPackInFromOut,
  type LearningPackIn,
  type LearningPackOut,
  type LearningPackVocabItem,
} from '@/shared/models/learning-pack.model';

@Component({
  selector: 'app-learning-pack-editor',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './learning-pack-editor.component.html',
  styleUrl: './learning-pack-editor.component.scss',
})
export class LearningPackEditorComponent implements OnInit {
  private readonly api = inject(ApiService);

  /** Topic id (always required for routing context). */
  readonly topicId = input.required<number>();
  /** When set, load/save unit-level pack; otherwise topic-level. */
  readonly unitId = input<number | null>(null);

  loading = signal(true);
  saving = signal(false);
  generating = signal(false);
  error = signal('');
  message = signal('');
  /** Optional extra instructions for AI generation. */
  aiIdea = signal('');
  draft = signal<LearningPackIn>(emptyLearningPack());

  ngOnInit(): void {
    const uid = this.unitId();
    this.loading.set(true);
    this.error.set('');
    const req =
      uid != null && uid > 0
        ? this.api.adminGetTopicUnitLearningPack(uid)
        : this.api.adminGetTopicLearningPack(this.topicId());
    req.pipe(finalize(() => this.loading.set(false))).subscribe({
      next: (pack: LearningPackOut) => this.draft.set(learningPackInFromOut(pack)),
      error: (err: { error?: { detail?: string } }) =>
        this.error.set(err?.error?.detail ?? 'Could not load learning pack.'),
    });
  }

  generateWithAi(): void {
    const uid = this.unitId();
    const tid = this.topicId();
    const idea = this.aiIdea().trim();
    this.generating.set(true);
    this.message.set('');
    this.error.set('');
    const req =
      uid != null && uid > 0
        ? this.api.adminAiDraftUnitLearningPack(uid, idea || null)
        : this.api.adminAiDraftTopicLearningPack(tid, idea || null);
    req.pipe(finalize(() => this.generating.set(false))).subscribe({
      next: (pack: LearningPackIn) => {
        this.draft.set(structuredClone(pack));
        this.message.set('AI draft loaded into the form. Review, then Save.');
      },
      error: (err: { error?: { detail?: string } }) =>
        this.error.set(err?.error?.detail ?? 'AI generation failed.'),
    });
  }

  save(): void {
    const uid = this.unitId();
    this.saving.set(true);
    this.message.set('');
    this.error.set('');
    const body = structuredClone(this.draft());
    const req =
      uid != null && uid > 0
        ? this.api.adminPutTopicUnitLearningPack(uid, body)
        : this.api.adminPutTopicLearningPack(this.topicId(), body);
    req.pipe(finalize(() => this.saving.set(false))).subscribe({
      next: (out: LearningPackOut) => {
        this.draft.set(learningPackInFromOut(out));
        this.message.set('Saved.');
      },
      error: (err: { error?: { detail?: string } }) =>
        this.error.set(err?.error?.detail ?? 'Save failed.'),
    });
  }

  protected bump(mutator: (d: LearningPackIn) => void): void {
    const next = structuredClone(this.draft());
    mutator(next);
    this.draft.set(next);
  }

  protected addVocab(): void {
    const row: LearningPackVocabItem = {
      term: '',
      meaning: '',
      collocations: [],
      example: null,
    };
    this.bump((d) => {
      d.vocabulary.push(row);
    });
  }

  protected removeVocab(i: number): void {
    this.bump((d) => {
      d.vocabulary.splice(i, 1);
    });
  }

  protected parseCollocations(s: string): string[] {
    return s
      .split(',')
      .map((x) => x.trim())
      .filter(Boolean)
      .slice(0, 8);
  }

  protected collocationsDisplayAt(i: number): string {
    return (this.draft().vocabulary[i]?.collocations ?? []).join(', ');
  }

  protected setCollocations(i: number, raw: string): void {
    this.bump((d) => {
      const row = d.vocabulary[i];
      if (row) row.collocations = this.parseCollocations(raw);
    });
  }

  protected patchVocab(i: number, patch: Partial<LearningPackVocabItem>): void {
    this.bump((d) => {
      const row = d.vocabulary[i];
      if (!row) return;
      Object.assign(row, patch);
    });
  }

  protected addPattern(): void {
    this.bump((d) => {
      d.sentence_patterns.push({ pattern: '', usage: '', example: '' });
    });
  }

  protected removePattern(i: number): void {
    this.bump((d) => d.sentence_patterns.splice(i, 1));
  }

  protected addMistake(): void {
    this.bump((d) => {
      d.common_mistakes.push({ mistake: '', fix: '', note: null });
    });
  }

  protected removeMistake(i: number): void {
    this.bump((d) => d.common_mistakes.splice(i, 1));
  }

  protected addModel(): void {
    this.bump((d) => {
      d.model_responses.push({ level: null, text: '' });
    });
  }

  protected removeModel(i: number): void {
    this.bump((d) => d.model_responses.splice(i, 1));
  }

  protected ideaPromptsText(): string {
    return (this.draft().idea_prompts ?? []).join('\n');
  }

  protected setIdeaPromptsText(v: string): void {
    this.bump((d) => {
      d.idea_prompts = v
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean);
    });
  }

  protected tipsText(): string {
    return (this.draft().tips ?? []).join('\n');
  }

  protected setTipsText(v: string): void {
    this.bump((d) => {
      d.tips = v
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean);
    });
  }

  protected patchPattern(
    i: number,
    patch: Partial<{ pattern: string; usage: string; example: string }>,
  ): void {
    this.bump((d) => {
      const row = d.sentence_patterns[i];
      if (row) Object.assign(row, patch);
    });
  }

  protected patchMistake(
    i: number,
    patch: Partial<{ mistake: string; fix: string; note: string | null }>,
  ): void {
    this.bump((d) => {
      const row = d.common_mistakes[i];
      if (row) Object.assign(row, patch);
    });
  }

  protected patchModel(
    i: number,
    patch: Partial<{ level: string | null; text: string }>,
  ): void {
    this.bump((d) => {
      const row = d.model_responses[i];
      if (row) Object.assign(row, patch);
    });
  }
}
