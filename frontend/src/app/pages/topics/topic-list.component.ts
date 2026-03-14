import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import { ApiService, Topic } from '../../shared/services/api.service';

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

  readonly api = inject(ApiService);
  readonly router = inject(Router);

  ngOnInit(): void {
    this.api
      .getTopics()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (t) => {
          this.topics.set(t);
        },
        error: () => {
          this.loading.set(false);
        },
      });
  }

  start(topic: Topic): void {
    this.router.navigate(['/conversation'], {
      queryParams: { topicId: topic.id, title: topic.title },
    });
  }
}
