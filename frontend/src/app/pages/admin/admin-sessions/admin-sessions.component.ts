import { CommonModule } from '@angular/common';
import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, ParamMap, Router, RouterLink } from '@angular/router';
import { NgSelectComponent } from '@ng-select/ng-select';
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap';
import { forkJoin, finalize } from 'rxjs';
import {
  AdminTopicSessionsPage,
  AdminUserOut,
  ApiService,
  Topic,
} from '../../../shared/services/api.service';

const PAGE_SIZE = 15;
const USERS_FOR_FILTER = 500;

export interface AdminSessionUserOption {
  id: number;
  label: string;
}

@Component({
  selector: 'app-admin-sessions',
  standalone: true,
  imports: [CommonModule, FormsModule, NgSelectComponent, RouterLink, NgbPaginationModule],
  templateUrl: './admin-sessions.component.html',
  styleUrls: ['./admin-sessions.component.scss'],
})
export class AdminSessionsComponent implements OnInit {
  /** Exposed for template (user dropdown cap). */
  readonly usersFilterLimit = USERS_FOR_FILTER;

  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  topics = signal<Topic[]>([]);
  users = signal<AdminUserOut[]>([]);
  metaLoading = signal(true);

  filterUserId = signal<number | null>(null);
  filterTopicId = signal<number | null>(null);

  sessionsData = signal<AdminTopicSessionsPage | null>(null);
  sessionsLoading = signal(false);
  error = signal('');
  currentPage = signal(1);
  readonly pageSize = PAGE_SIZE;
  deletingSessionId = signal<number | null>(null);

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

  readonly userSelectItems = computed((): AdminSessionUserOption[] =>
    this.users().map((u) => ({
      id: u.id,
      label: `${u.email} (@${u.username})`,
    })),
  );

  ngOnInit(): void {
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((qp) => {
      this.applyFiltersFromQuery(qp);
      this.loadSessionsPage(1);
    });

    forkJoin({
      topics: this.api.getTopics(),
      users: this.api.adminListUsers(1, USERS_FOR_FILTER),
    })
      .pipe(finalize(() => this.metaLoading.set(false)))
      .subscribe({
        next: ({ topics, users }) => {
          this.topics.set(topics);
          this.users.set(users.items);
        },
        error: () => this.error.set('Could not load topics or users for filters.'),
      });
  }

  private applyFiltersFromQuery(qp: ParamMap): void {
    const ur = qp.get('user_id');
    const tr = qp.get('topic_id');
    const u = ur != null ? Number(ur) : NaN;
    const t = tr != null ? Number(tr) : NaN;
    this.filterUserId.set(Number.isFinite(u) && u > 0 ? u : null);
    this.filterTopicId.set(Number.isFinite(t) && t > 0 ? t : null);
  }

  private syncQueryToUrl(): void {
    const q: Record<string, number> = {};
    const u = this.filterUserId();
    const t = this.filterTopicId();
    if (u != null) q['user_id'] = u;
    if (t != null) q['topic_id'] = t;
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: Object.keys(q).length ? q : {},
      replaceUrl: true,
    });
  }

  onUserFilterChange(value: number | null | undefined): void {
    this.filterUserId.set(value ?? null);
    this.syncQueryToUrl();
  }

  onTopicFilterChange(value: number | null | undefined): void {
    this.filterTopicId.set(value ?? null);
    this.syncQueryToUrl();
  }

  clearFilters(): void {
    this.filterUserId.set(null);
    this.filterTopicId.set(null);
    void this.router.navigate([], { relativeTo: this.route, queryParams: {}, replaceUrl: true });
  }

  loadSessionsPage(page: number): void {
    this.sessionsLoading.set(true);
    this.error.set('');
    this.api
      .adminListAllSessions(page, this.pageSize, {
        userId: this.filterUserId(),
        topicId: this.filterTopicId(),
      })
      .pipe(finalize(() => this.sessionsLoading.set(false)))
      .subscribe({
        next: (res) => {
          this.sessionsData.set(res);
          this.currentPage.set(page);
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Could not load sessions.');
          this.sessionsData.set(null);
        },
      });
  }

  goToPage(page: number): void {
    const max = this.totalPages();
    if (page < 1 || page > max) return;
    this.loadSessionsPage(page);
  }

  deleteSession(topicId: number, sessionId: number, event?: Event): void {
    event?.stopPropagation();
    const ok = window.confirm('Delete this session? This cannot be undone.');
    if (!ok) return;
    this.deletingSessionId.set(sessionId);
    this.api
      .adminDeleteTopicSession(topicId, sessionId)
      .pipe(finalize(() => this.deletingSessionId.set(null)))
      .subscribe({
        next: () => {
          const items = this.sessionsData()?.items ?? [];
          const page = this.currentPage();
          if (items.length <= 1 && page > 1) {
            this.goToPage(page - 1);
          } else {
            this.loadSessionsPage(page);
          }
        },
        error: (err) => this.error.set(err?.error?.detail ?? 'Could not delete session.'),
      });
  }
}
