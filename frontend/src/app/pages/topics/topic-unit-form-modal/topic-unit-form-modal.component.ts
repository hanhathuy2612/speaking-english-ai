import { CommonModule } from '@angular/common';
import { Component, inject, InjectionToken } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NgbActiveModal, NgbModalModule } from '@ng-bootstrap/ng-bootstrap';
import { finalize } from 'rxjs';
import { ApiService } from '../../../shared/services/api.service';

export interface TopicUnitFormModalData {
  topicId: number;
  suggestedSortOrder: number;
}

export const TOPIC_UNIT_FORM_MODAL_DATA = new InjectionToken<TopicUnitFormModalData>(
  'TopicUnitFormModalData',
);

@Component({
  selector: 'app-topic-unit-form-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, NgbModalModule],
  templateUrl: './topic-unit-form-modal.component.html',
  styleUrls: ['./topic-unit-form-modal.component.scss'],
})
export class TopicUnitFormModalComponent {
  private readonly activeModal = inject(NgbActiveModal);
  private readonly api = inject(ApiService);
  private readonly data = inject(TOPIC_UNIT_FORM_MODAL_DATA);

  sortOrder = this.data.suggestedSortOrder;
  title = '';
  objective = '';
  promptHint = '';
  minTurns: number | null = null;
  minAvg: number | null = null;
  maxScoredTurns: number | null = null;
  saving = false;
  error = '';

  cancel(): void {
    this.activeModal.dismiss();
  }

  submit(): void {
    const t = this.title.trim();
    const o = this.objective.trim();
    const h = this.promptHint.trim();
    if (!t || !o || !h) {
      this.error = 'Title, objective, and tutor hint are required.';
      return;
    }
    this.error = '';
    this.saving = true;
    this.api
      .adminCreateTopicUnit(this.data.topicId, {
        sort_order: this.sortOrder,
        title: t,
        objective: o,
        prompt_hint: h,
        min_turns_to_complete: this.minTurns,
        min_avg_overall: this.minAvg,
        max_scored_turns: this.maxScoredTurns,
      })
      .pipe(finalize(() => (this.saving = false)))
      .subscribe({
        next: (created) => this.activeModal.close(created),
        error: () => (this.error = 'Could not create step.'),
      });
  }
}
