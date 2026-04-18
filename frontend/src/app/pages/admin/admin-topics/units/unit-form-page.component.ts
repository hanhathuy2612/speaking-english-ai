import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { ApiService } from '../../../../shared/services/api.service';
import {
  TopicUnitFormModalComponent,
  type TopicUnitFormModalData,
} from '../../../topics/topic-unit-form-modal/topic-unit-form-modal.component';
import { LearningPackEditorComponent } from '../../learning-pack-editor/learning-pack-editor.component';

@Component({
  selector: 'app-admin-topic-unit-form-page',
  imports: [CommonModule, RouterLink, TopicUnitFormModalComponent, LearningPackEditorComponent],
  templateUrl: './unit-form-page.component.html',
  styleUrls: ['./unit-form-page.component.scss'],
})
export class AdminTopicUnitFormPageComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(ApiService);

  topicId = signal(0);
  /** Set when editing an existing step (for learning pack API). */
  editUnitId = signal<number | null>(null);
  isEdit = signal(false);
  formPayload = signal<TopicUnitFormModalData | null>(null);
  loading = signal(true);
  error = signal('');

  ngOnInit(): void {
    const topicId = Number(this.route.snapshot.paramMap.get('topicId'));
    const unitIdRaw = this.route.snapshot.paramMap.get('unitId');

    if (!Number.isFinite(topicId) || topicId <= 0) {
      void this.router.navigate(['/admin/topics']);
      return;
    }
    this.topicId.set(topicId);

    const isEdit = unitIdRaw != null && unitIdRaw !== '';
    const unitId = isEdit ? Number(unitIdRaw) : NaN;
    if (isEdit && (!Number.isFinite(unitId) || unitId <= 0)) {
      this.loading.set(false);
      this.error.set('Invalid step.');
      return;
    }
    this.isEdit.set(isEdit);
    this.editUnitId.set(isEdit ? unitId : null);

    this.api
      .getTopicRoadmap(topicId)
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (roadmap) => {
          const units = [...roadmap.units]
            .map((item) => item.unit)
            .sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
          if (isEdit) {
            const unit = units.find((u) => u.id === unitId);
            if (!unit) {
              this.error.set('Step not found.');
              return;
            }
            this.formPayload.set({
              topicId,
              suggestedSortOrder: unit.sort_order,
              unit,
            });
          } else {
            const nextOrder = units.length ? Math.max(...units.map((u) => u.sort_order), 0) + 1 : 1;
            this.formPayload.set({
              topicId,
              suggestedSortOrder: nextOrder,
            });
          }
        },
        error: (err) => this.error.set(err?.error?.detail ?? 'Could not load topic.'),
      });
  }
}
