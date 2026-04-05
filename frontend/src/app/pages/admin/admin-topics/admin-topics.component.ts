import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { NgbModal, NgbModalModule, NgbModalRef } from '@ng-bootstrap/ng-bootstrap';
import { finalize } from 'rxjs';
import {
  BreadcrumbComponent,
  BreadcrumbItem,
} from '../../../shared/components/breadcrumb/breadcrumb.component';
import { formatIeltsBand, resolveIeltsBand } from '../../../shared/ielts-levels';
import { ApiService, Topic } from '../../../shared/services/api.service';
import { TopicFormModalComponent } from '../../topics/topic-form-modal/topic-form-modal.component';

@Component({
  selector: 'app-admin-topics',
  standalone: true,
  imports: [CommonModule, RouterLink, NgbModalModule, BreadcrumbComponent],
  templateUrl: './admin-topics.component.html',
  styleUrls: ['./admin-topics.component.scss'],
})
export class AdminTopicsComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly modal = inject(NgbModal);

  topics = signal<Topic[]>([]);
  loading = signal(false);
  error = signal('');
  deletingTopicId = signal<number | null>(null);

  readonly breadcrumbItems: readonly BreadcrumbItem[] = [
    { label: 'Admin', link: '/admin' },
    { label: 'Topics', link: '/admin/topics' },
  ];

  private modalRef: NgbModalRef | null = null;

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.api
      .getTopics()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (items) => this.topics.set(items),
        error: (err) => this.error.set(err?.error?.detail ?? 'Could not load topics.'),
      });
  }

  topicLevelLabel(t: Topic): string {
    const n = resolveIeltsBand(t.level);
    if (n != null) return `Band ${formatIeltsBand(n)}`;
    return (t.level ?? '').trim() || 'General';
  }

  openCreateForm(): void {
    this.modalRef = this.modal.open(TopicFormModalComponent, {
      size: 'lg',
      backdrop: 'static',
      keyboard: false,
    });
    this.modalRef.closed.subscribe((created) => {
      this.modalRef = null;
      if (created != null) this.load();
    });
    this.modalRef.dismissed.subscribe(() => {
      this.modalRef = null;
    });
  }

  openManageSteps(topic: Topic): void {
    void this.router.navigate(['/admin/topics', topic.id, 'units']);
  }

  deleteTopic(topic: Topic): void {
    const ok = window.confirm(
      `Delete topic "${topic.title}"? This will also remove related sessions and roadmap steps.`,
    );
    if (!ok) return;
    this.deletingTopicId.set(topic.id);
    this.api
      .adminDeleteTopic(topic.id)
      .pipe(finalize(() => this.deletingTopicId.set(null)))
      .subscribe({
        next: () => this.topics.update((list) => list.filter((x) => x.id !== topic.id)),
        error: (err) => this.error.set(err?.error?.detail ?? 'Could not delete topic.'),
      });
  }
}
