import { NgSelectComponent } from '@ng-select/ng-select';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  Component,
  inject,
  InjectionToken,
  signal,
  computed,
} from '@angular/core';
import { NgbActiveModal, NgbModalModule } from '@ng-bootstrap/ng-bootstrap';
import { finalize } from 'rxjs';
import {
  IELTS_SPEAKING_BAND_VALUES,
  normalizeIeltsLevelInput,
} from '../../../shared/ielts-levels';
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
export class TopicFormModalComponent {
  private readonly activeModal = inject(NgbActiveModal);
  private readonly api = inject(ApiService);
  private readonly topic: Topic | null = inject(TOPIC_FORM_MODAL_DATA, { optional: true }) ?? null;

  readonly isEdit = computed(() => this.topic != null);
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
  readonly title = signal(this.topic?.title ?? '');
  readonly description = signal(this.topic?.description ?? '');
  readonly level = signal(normalizeLevel(this.topic?.level ?? ''));
  readonly error = signal('');
  readonly saving = signal(false);

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
    this.activeModal.dismiss();
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
    if (this.topic) {
      this.api
        .updateTopic(this.topic.id, payload)
        .pipe(finalize(() => this.saving.set(false)))
        .subscribe({
          next: (updated) => this.activeModal.close(updated),
          error: (err) => {
            this.error.set(err?.error?.detail ?? 'Failed to update topic.');
          },
        });
    } else {
      this.api
        .createTopic(payload)
        .pipe(finalize(() => this.saving.set(false)))
        .subscribe({
          next: (created) => this.activeModal.close(created),
          error: (err) => {
            this.error.set(err?.error?.detail ?? 'Failed to create topic.');
          },
        });
    }
  }
}
