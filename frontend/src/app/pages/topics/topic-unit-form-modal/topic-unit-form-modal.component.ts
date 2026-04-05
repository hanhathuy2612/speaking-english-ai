import { CommonModule } from '@angular/common';
import { Component, computed, inject, InjectionToken, input, OnInit, signal } from '@angular/core';
import { form, FormField, maxLength, min, validate } from '@angular/forms/signals';
import { Router } from '@angular/router';
import { NgbActiveModal, NgbModalModule } from '@ng-bootstrap/ng-bootstrap';
import { finalize } from 'rxjs';
import { ApiService, TopicUnitDto } from '../../../shared/services/api.service';

export interface TopicUnitFormModalData {
  topicId: number;
  suggestedSortOrder: number;
  unit?: TopicUnitDto | null;
}

export interface TopicUnitFormModel {
  aiIdea: string;
  sortOrder: number;
  title: string;
  objective: string;
  promptHint: string;
  minTurns: number | null;
  minAvg: number | null;
  maxScoredTurns: number | null;
}

export const TOPIC_UNIT_FORM_MODAL_DATA = new InjectionToken<TopicUnitFormModalData | null>(
  'TopicUnitFormModalData',
);

@Component({
  selector: 'app-topic-unit-form-modal',
  standalone: true,
  imports: [CommonModule, FormField, NgbModalModule],
  templateUrl: './topic-unit-form-modal.component.html',
  styleUrls: ['./topic-unit-form-modal.component.scss'],
})
export class TopicUnitFormModalComponent implements OnInit {
  private readonly activeModal = inject(NgbActiveModal, { optional: true });
  private readonly router = inject(Router);
  private readonly api = inject(ApiService);
  private readonly injectedData = inject(TOPIC_UNIT_FORM_MODAL_DATA, { optional: true });

  /** Khi nhúng trang admin; modal roadmap vẫn dùng token inject. */
  embeddedData = input<TopicUnitFormModalData | null>(null);

  readonly isModalShell = this.activeModal != null;

  private resolveData(): TopicUnitFormModalData {
    const emb = this.embeddedData();
    if (emb) return emb;
    if (this.injectedData) return this.injectedData;
    throw new Error('TopicUnitFormModalComponent: missing form data');
  }

  private readonly formUnit = signal<TopicUnitDto | null>(null);

  readonly isEdit = computed(() => this.formUnit() != null);
  readonly modalTitle = computed(() => (this.isEdit() ? 'Edit roadmap step' : 'Add roadmap step'));

  readonly unitModel = signal<TopicUnitFormModel>({
    aiIdea: '',
    sortOrder: 1,
    title: '',
    objective: '',
    promptHint: '',
    minTurns: null,
    minAvg: null,
    maxScoredTurns: null,
  });

  readonly unitForm = form(this.unitModel, (p) => {
    validate(p.title, ({ value }) =>
      !value().trim() ? { kind: 'required', message: 'Title is required.' } : null,
    );
    maxLength(p.title, 255, { message: 'Title must be at most 255 characters.' });
    validate(p.objective, ({ value }) =>
      !value().trim() ? { kind: 'required', message: 'Objective is required.' } : null,
    );
    validate(p.promptHint, ({ value }) =>
      !value().trim() ? { kind: 'required', message: 'Tutor hint is required.' } : null,
    );
    min(p.sortOrder, 0, { message: 'Sort order cannot be negative.' });
  });

  readonly saving = signal(false);
  readonly aiGenerating = signal(false);
  readonly errorSignal = signal('');

  ngOnInit(): void {
    const data = this.resolveData();
    const u = data.unit ?? null;
    this.formUnit.set(u);
    this.unitModel.set({
      aiIdea: '',
      sortOrder: u?.sort_order ?? data.suggestedSortOrder,
      title: u?.title ?? '',
      objective: u?.objective ?? '',
      promptHint: u?.prompt_hint ?? '',
      minTurns: u?.min_turns_to_complete ?? null,
      minAvg: u?.min_avg_overall ?? null,
      maxScoredTurns: u?.max_scored_turns ?? null,
    });
  }

  submitLabel(): string {
    if (this.saving()) {
      return this.isEdit() ? 'Saving…' : 'Creating…';
    }
    return this.isEdit() ? 'Save' : 'Create';
  }

  cancel(): void {
    if (this.activeModal) this.activeModal.dismiss();
    else {
      const d = this.resolveData();
      void this.router.navigate(['/admin/topics', d.topicId, 'units']);
    }
  }

  onFormSubmit(event: Event): void {
    event.preventDefault();
    this.errorSignal.set('');
    if (this.unitForm().invalid()) {
      this.unitForm().markAsTouched();
      return;
    }
    this.runSave();
  }

  private runSave(): void {
    const data = this.resolveData();
    const m = this.unitModel();
    const payload = {
      sort_order: m.sortOrder,
      title: m.title.trim(),
      objective: m.objective.trim(),
      prompt_hint: m.promptHint.trim(),
      min_turns_to_complete: m.minTurns,
      min_avg_overall: m.minAvg,
      max_scored_turns: m.maxScoredTurns,
    };
    const u = this.formUnit();
    const request$ = u
      ? this.api.adminUpdateTopicUnit(data.topicId, u.id, payload)
      : this.api.adminCreateTopicUnit(data.topicId, payload);

    this.saving.set(true);
    request$.pipe(finalize(() => this.saving.set(false))).subscribe({
      next: (saved) => {
        if (this.activeModal) this.activeModal.close(saved);
        else void this.router.navigate(['/admin/topics', data.topicId, 'units']);
      },
      error: (err) => {
        this.errorSignal.set(err?.error?.detail ?? 'Could not save step.');
      },
    });
  }

  generateWithAi(): void {
    if (this.aiGenerating()) return;
    this.errorSignal.set('');
    this.aiGenerating.set(true);
    const topicId = this.resolveData().topicId;
    const idea = this.unitModel().aiIdea;
    this.api
      .adminGenerateTopicUnitDraft(topicId, idea)
      .pipe(finalize(() => this.aiGenerating.set(false)))
      .subscribe({
        next: (draft) => {
          this.unitModel.update((prev) => ({
            ...prev,
            title: draft.title ?? '',
            objective: draft.objective ?? '',
            promptHint: draft.prompt_hint ?? '',
            minTurns: draft.min_turns_to_complete ?? null,
            minAvg: draft.min_avg_overall ?? null,
            maxScoredTurns: draft.max_scored_turns ?? null,
          }));
        },
        error: (err) => {
          this.errorSignal.set(err?.error?.detail ?? 'Could not generate step draft with AI.');
        },
      });
  }
}
