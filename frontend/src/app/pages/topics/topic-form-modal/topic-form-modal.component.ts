import { NgSelectComponent } from '@ng-select/ng-select';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Component, computed, inject, InjectionToken, input, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { NgbActiveModal, NgbModalModule } from '@ng-bootstrap/ng-bootstrap';
import { finalize } from 'rxjs';
import { IELTS_SPEAKING_BAND_VALUES, normalizeIeltsLevelInput } from '../../../shared/ielts-levels';
import { ApiService, Topic } from '../../../shared/services/api.service';

/** Khi có giá trị = edit, không provide hoặc null = create */
export const TOPIC_FORM_MODAL_DATA = new InjectionToken<Topic | null>('TopicFormModalData');

const LEVEL_OPTIONS = [
  { value: '', label: 'General' },
  ...IELTS_SPEAKING_BAND_VALUES.map((b) => ({ value: b, label: `Band ${b}` })),
];

function normalizeLevel(level: string | null | undefined): string {
  return normalizeIeltsLevelInput(level);
}

@Component({
  selector: 'app-topic-form-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, NgSelectComponent, NgbModalModule],
  styleUrls: ['./topic-form-modal.component.scss'],
  templateUrl: './topic-form-modal.component.html',
})
export class TopicFormModalComponent implements OnInit {
  private readonly activeModal = inject(NgbActiveModal, { optional: true });
  private readonly router = inject(Router);
  private readonly api = inject(ApiService);
  private readonly injectedTopic = inject(TOPIC_FORM_MODAL_DATA, { optional: true }) ?? null;

  /** Khi nhúng ở trang admin (không dùng modal), truyền topic qua input. */
  embeddedTopic = input<Topic | null>(null);

  readonly isModalShell = this.activeModal != null;

  readonly formTopic = computed(() => this.embeddedTopic() ?? this.injectedTopic);

  readonly isEdit = computed(() => this.formTopic() != null);
  readonly modalTitle = computed(() => (this.isEdit() ? 'Edit topic' : 'Create new topic'));
  readonly submitLabel = computed(() =>
    this.saving()
      ? this.isEdit()
        ? 'Saving…'
        : 'Creating…'
      : this.isEdit()
        ? 'Save'
        : 'Create topic',
  );

  readonly levelOptions = LEVEL_OPTIONS;
  readonly title = signal('');
  readonly description = signal('');
  readonly level = signal('');
  readonly error = signal('');
  readonly saving = signal(false);
  readonly aiIdea = signal('');
  readonly aiGenerating = signal(false);

  ngOnInit(): void {
    const t = this.formTopic();
    if (t) this.patchFromTopic(t);
  }

  private patchFromTopic(t: Topic): void {
    this.title.set(t.title ?? '');
    this.description.set(t.description ?? '');
    this.level.set(normalizeLevel(t.level ?? ''));
  }

  onTitleInput(value: string): void {
    this.title.set(value);
  }

  onDescriptionInput(value: string): void {
    this.description.set(value);
  }

  onLevelChange(value: string | null): void {
    this.level.set(value ?? '');
  }

  cancel(): void {
    if (this.activeModal) this.activeModal.dismiss();
    else void this.router.navigate(['/admin/topics']);
  }

  generateWithAi(): void {
    if (this.aiGenerating()) return;
    this.error.set('');
    this.aiGenerating.set(true);
    this.api
      .adminGenerateTopicDraft(this.aiIdea())
      .pipe(finalize(() => this.aiGenerating.set(false)))
      .subscribe({
        next: (draft) => {
          this.title.set(draft.title ?? '');
          this.description.set(draft.description ?? '');
          this.level.set(normalizeLevel(draft.level ?? ''));
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Failed to generate topic draft with AI.');
        },
      });
  }

  submit(): void {
    const title = this.title().trim();
    if (!title) {
      this.error.set('Title is required.');
      return;
    }
    this.error.set('');
    this.saving.set(true);
    const payload = {
      title,
      description: this.description().trim() || null,
      level: this.level().trim() || null,
    };
    const topic = this.formTopic();
    if (topic) {
      this.api
        .updateTopic(topic.id, payload)
        .pipe(finalize(() => this.saving.set(false)))
        .subscribe({
          next: (updated) => {
            if (this.activeModal) this.activeModal.close(updated);
            else void this.router.navigate(['/admin/topics']);
          },
          error: (err) => {
            this.error.set(err?.error?.detail ?? 'Failed to update topic.');
          },
        });
    } else {
      this.api
        .createTopic(payload)
        .pipe(finalize(() => this.saving.set(false)))
        .subscribe({
          next: (created) => {
            if (this.activeModal) this.activeModal.close(created);
            else void this.router.navigate(['/admin/topics']);
          },
          error: (err) => {
            this.error.set(err?.error?.detail ?? 'Failed to create topic.');
          },
        });
    }
  }
}
