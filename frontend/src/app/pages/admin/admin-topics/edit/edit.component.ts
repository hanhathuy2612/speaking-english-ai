import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { ApiService, Topic } from '../../../../shared/services/api.service';
import { TopicFormModalComponent } from '../../../topics/topic-form-modal/topic-form-modal.component';
import { LearningPackEditorComponent } from '../../learning-pack-editor/learning-pack-editor.component';

@Component({
  selector: 'app-admin-topic-edit',
  imports: [CommonModule, RouterLink, TopicFormModalComponent, LearningPackEditorComponent],
  templateUrl: './edit.component.html',
  styleUrls: ['./edit.component.scss'],
})
export class AdminTopicEditComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(ApiService);

  topic = signal<Topic | null>(null);
  loading = signal(true);
  error = signal('');

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('topicId'));
    if (!Number.isFinite(id) || id <= 0) {
      void this.router.navigate(['/admin/topics']);
      return;
    }
    this.api
      .getTopics()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (list) => {
          const t = list.find((x) => x.id === id);
          if (!t) {
            this.error.set('Topic not found.');
            return;
          }
          this.topic.set(t);
        },
        error: (err) => this.error.set(err?.error?.detail ?? 'Could not load topic.'),
      });
  }
}
