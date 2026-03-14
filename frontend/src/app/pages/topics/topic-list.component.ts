import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import { ApiService, Topic } from '../../shared/services/api.service';

const LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1'] as const;

@Component({
  selector: 'app-topic-list',
  standalone: true,
  imports: [CommonModule],
  styleUrls: ['./topic-list.component.scss'],
  templateUrl: './topic-list.component.html',
})
export class TopicListComponent implements OnInit {
  topics = signal<Topic[]>([]);
  loading = signal(false);
  showCreateForm = signal(false);
  newTitle = signal('');
  newDescription = signal('');
  newLevel = signal<string>('');
  createError = signal('');
  creating = signal(false);

  readonly levels = LEVELS;
  readonly api = inject(ApiService);
  readonly router = inject(Router);

  ngOnInit(): void {
    this.loadTopics();
  }

  loadTopics(): void {
    this.loading.set(true);
    this.api
      .getTopics()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (t) => this.topics.set(t),
        error: () => this.loading.set(false),
      });
  }

  start(topic: Topic): void {
    this.router.navigate(['/conversation'], {
      queryParams: { topicId: topic.id, title: topic.title },
    });
  }

  openCreateForm(): void {
    this.showCreateForm.set(true);
    this.newTitle.set('');
    this.newDescription.set('');
    this.newLevel.set('');
    this.createError.set('');
  }

  cancelCreate(): void {
    this.showCreateForm.set(false);
    this.createError.set('');
  }

  submitCreate(): void {
    const title = this.newTitle().trim();
    if (!title) {
      this.createError.set('Title is required.');
      return;
    }
    this.createError.set('');
    this.creating.set(true);
    this.api
      .createTopic({
        title,
        description: this.newDescription().trim() || null,
        level: this.newLevel().trim() || null,
      })
      .pipe(finalize(() => this.creating.set(false)))
      .subscribe({
        next: () => {
          this.loadTopics();
          this.showCreateForm.set(false);
          this.newTitle.set('');
          this.newDescription.set('');
          this.newLevel.set('');
        },
        error: (err) => {
          this.createError.set(err?.error?.detail ?? 'Failed to create topic.');
        },
      });
  }
}
