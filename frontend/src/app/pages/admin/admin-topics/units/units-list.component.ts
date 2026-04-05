import { CommonModule } from '@angular/common';
import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap';
import { finalize } from 'rxjs';
import {
  AdminTopicSessionsPage,
  ApiService,
  TopicUnitDto,
} from '../../../../shared/services/api.service';

const SESSIONS_PAGE_SIZE = 15;

@Component({
  selector: 'app-admin-topic-units',
  imports: [CommonModule, RouterLink, NgbPaginationModule],
  templateUrl: './units-list.component.html',
  styleUrls: ['./units-list.component.scss'],
})
export class AdminTopicUnitsComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);

  topicId = signal(0);
  topicTitle = signal('Topic');
  units = signal<TopicUnitDto[]>([]);
  loading = signal(false);
  error = signal('');
  deletingUnitId = signal<number | null>(null);

  sessionsData = signal<AdminTopicSessionsPage | null>(null);
  sessionsLoading = signal(false);
  sessionsError = signal('');
  sessionsPage = signal(1);
  readonly sessionsPageSize = SESSIONS_PAGE_SIZE;

  readonly sessionsTotalPages = computed(() => {
    const total = this.sessionsData()?.total ?? 0;
    return total === 0 ? 1 : Math.ceil(total / this.sessionsPageSize);
  });

  readonly sessionsPaginationRange = computed(() => {
    const total = this.sessionsData()?.total ?? 0;
    const page = this.sessionsPage();
    const start = total === 0 ? 0 : (page - 1) * this.sessionsPageSize + 1;
    const end = Math.min(page * this.sessionsPageSize, total);
    return { start, end, total };
  });

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('topicId'));
    if (!Number.isFinite(id) || id <= 0) {
      void this.router.navigate(['/admin/users']);
      return;
    }
    this.topicId.set(id);
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.api
      .getTopicRoadmap(this.topicId())
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (roadmap) => {
          this.topicTitle.set(roadmap.topic_title);
          this.units.set(
            [...roadmap.units]
              .map((item) => item.unit)
              .sort((a, b) => a.sort_order - b.sort_order || a.id - b.id),
          );
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Could not load topic steps.');
        },
      });
  }

  deleteUnit(unit: TopicUnitDto): void {
    const ok = globalThis.confirm(`Delete step "${unit.title}"? This cannot be undone.`);
    if (!ok) return;
    this.deletingUnitId.set(unit.id);
    this.api
      .adminDeleteTopicUnit(this.topicId(), unit.id)
      .pipe(finalize(() => this.deletingUnitId.set(null)))
      .subscribe({
        next: () => this.load(),
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Could not delete step.');
        },
      });
  }
}
