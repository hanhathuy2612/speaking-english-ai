import { ProgressService, SessionsPageResponse } from '@/app/shared/services/progress.service';
import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap';
import { finalize } from 'rxjs';
import { ApiService, Topic } from '../../../shared/services/api.service';

const PAGE_SIZE = 15;

@Component({
  selector: 'app-topic-session-history',
  standalone: true,
  imports: [CommonModule, RouterLink, NgbPaginationModule],
  styleUrls: ['./topic-session-history.component.scss'],
  templateUrl: './topic-session-history.component.html',
})
export class TopicSessionHistoryComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(ApiService);
  private readonly progress = inject(ProgressService);

  topicId = signal(0);
  topicTitle = signal('');
  sessionsData = signal<SessionsPageResponse | null>(null);
  loading = signal(true);
  newChatBusy = signal(false);
  newChatError = signal('');
  currentPage = signal(1);
  readonly pageSize = PAGE_SIZE;

  readonly totalPages = computed(() => {
    const total = this.sessionsData()?.total ?? 0;
    return total === 0 ? 1 : Math.ceil(total / this.pageSize);
  });

  readonly paginationRange = computed(() => {
    const total = this.sessionsData()?.total ?? 0;
    const page = this.currentPage();
    const start = total === 0 ? 0 : (page - 1) * this.pageSize + 1;
    const end = Math.min(page * this.pageSize, total);
    return { start, end, total };
  });

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('topicId'));
    if (!Number.isFinite(id) || id <= 0) {
      void this.router.navigate(['/topics']);
      return;
    }
    this.topicId.set(id);
    this.api.getTopics().subscribe({
      next: (list: Topic[]) => {
        const t = list.find((x) => x.id === id);
        this.topicTitle.set(t?.title ?? 'Topic');
      },
      error: () => this.topicTitle.set('Topic'),
    });
    this.loadPage(1);
  }

  loadPage(page: number): void {
    const tid = this.topicId();
    this.loading.set(true);
    this.progress
      .getTopicSessions(tid, page, this.pageSize)
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (res) => {
          this.sessionsData.set(res);
          this.currentPage.set(page);
        },
        error: () => void this.router.navigate(['/topics', tid, 'roadmap']),
      });
  }

  goToPage(page: number): void {
    const totalP = this.totalPages();
    if (page < 1 || page > totalP) return;
    this.loadPage(page);
  }

  openSession(s: { id: number; topic_id: number; topic_title: string }): void {
    void this.router.navigate(['/conversation'], {
      queryParams: { topicId: s.topic_id, title: s.topic_title, sessionId: s.id },
    });
  }

  startNewConversation(): void {
    if (this.newChatBusy()) return;
    const tid = this.topicId();
    const title = this.topicTitle();
    this.newChatError.set('');
    this.newChatBusy.set(true);
    this.api
      .postCreateSession({ topic_id: tid })
      .pipe(finalize(() => this.newChatBusy.set(false)))
      .subscribe({
        next: (res) => {
          void this.router.navigate(['/conversation'], {
            queryParams: { topicId: tid, title, sessionId: res.id },
          });
        },
        error: (err: { error?: { detail?: unknown } }) => {
          const d = err?.error?.detail;
          let msg = 'Could not create a session. Try again.';
          if (typeof d === 'string') msg = d;
          else if (Array.isArray(d) && d.length > 0 && typeof (d[0] as { msg?: string }).msg === 'string') {
            msg = (d[0] as { msg: string }).msg;
          }
          this.newChatError.set(msg);
        },
      });
  }

  deleteSession(sessionId: number, $event?: Event): void {
    $event?.stopPropagation();
    const tid = this.topicId();
    this.progress.deleteSession(sessionId).subscribe({
      next: () => {
        const items = this.sessionsData()?.items ?? [];
        const page = this.currentPage();
        if (items.length <= 1 && page > 1) {
          this.goToPage(page - 1);
        } else {
          this.loadPage(page);
        }
      },
    });
  }
}
