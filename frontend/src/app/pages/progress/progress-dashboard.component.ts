import { ProgressService, SessionsPageResponse } from '@/app/shared/services/progress.service';
import { CommonModule } from '@angular/common';
import {
  AfterViewInit,
  Component,
  computed,
  ElementRef,
  inject,
  OnInit,
  signal,
  viewChild,
} from '@angular/core';
import { Router } from '@angular/router';
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap';
import { finalize } from 'rxjs';
import { ProgressSummary } from '../../shared/services/api.service';

declare const Chart: any;

const PAGE_SIZE = 10;

@Component({
  selector: 'app-progress-dashboard',
  standalone: true,
  imports: [CommonModule, NgbPaginationModule],
  styleUrls: ['./progress-dashboard.component.scss'],
  templateUrl: './progress-dashboard.component.html',
})
export class ProgressDashboardComponent implements OnInit, AfterViewInit {
  private readonly router = inject(Router);
  readonly lineChartRef = viewChild<ElementRef<HTMLCanvasElement>>('lineChart');
  readonly radarChartRef = viewChild<ElementRef<HTMLCanvasElement>>('radarChart');

  data = signal<ProgressSummary | undefined>(undefined);
  loading = signal(false);

  sessionsData = signal<SessionsPageResponse | null>(null);
  loadingSessions = signal(false);
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

  readonly progressService = inject(ProgressService);

  ngOnInit(): void {
    this.loading.set(true);
    this.progressService
      .getProgressSummary()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (d) => this.data.set(d),
        error: () => this.loading.set(false),
      });

    this.loadSessions(1);
  }

  loadSessions(page: number): void {
    this.loadingSessions.set(true);
    this.progressService
      .getSessions(page, this.pageSize)
      .pipe(finalize(() => this.loadingSessions.set(false)))
      .subscribe({
        next: (res) => {
          this.sessionsData.set(res);
          this.currentPage.set(page);
        },
      });
  }

  goToPage(page: number): void {
    const totalP = this.totalPages();
    if (page < 1 || page > totalP) return;
    this.currentPage.set(page);
    this.loadSessions(page);
  }

  openSession(s: { id: number; topic_id: number; topic_title: string }): void {
    void this.router.navigate(['/conversation'], {
      queryParams: { topicId: s.topic_id, title: s.topic_title, sessionId: s.id },
    });
  }

  ngAfterViewInit(): void {
    const check = setInterval(() => {
      if (this.data() && typeof Chart !== 'undefined') {
        clearInterval(check);
        // Defer so canvas refs are available after @if renders
        setTimeout(() => this._renderCharts(), 0);
      }
    }, 200);
  }

  deleteSession(sessionId: number, $event?: Event): void {
    $event?.stopPropagation();
    this.progressService.deleteSession(sessionId).subscribe({
      next: () => {
        const items = this.sessionsData()?.items ?? [];
        const page = this.currentPage();
        if (items.length <= 1 && page > 1) {
          this.goToPage(page - 1);
        } else {
          this.loadSessions(page);
        }
      },
    });
  }

  private _renderCharts(): void {
    const lineEl = this.lineChartRef()?.nativeElement;
    const radarEl = this.radarChartRef()?.nativeElement;
    if (!this.data() || !lineEl || !radarEl) return;

    // Line chart – daily minutes
    new Chart(lineEl, {
      type: 'line',
      data: {
        labels: this.data()?.daily_minutes.map((d) => d.date),
        datasets: [
          {
            label: 'Minutes',
            data: this.data()?.daily_minutes.map((d) => d.minutes),
            borderColor: '#58a6ff',
            backgroundColor: 'rgba(88,166,255,0.12)',
            tension: 0.4,
            fill: true,
            pointRadius: 4,
          },
        ],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
          y: {
            ticks: { color: '#8b949e' },
            grid: { color: '#21262d' },
            beginAtZero: true,
          },
        },
      },
    });

    // Radar chart – skill scores
    const avg = this.data()?.avg_scores;
    new Chart(radarEl, {
      type: 'radar',
      data: {
        labels: ['Fluency', 'Vocabulary', 'Grammar', 'Overall'],
        datasets: [
          {
            label: 'Your scores',
            data: avg ? [avg.fluency, avg.vocabulary, avg.grammar, avg.overall] : [0, 0, 0, 0],
            borderColor: '#58a6ff',
            backgroundColor: 'rgba(88,166,255,0.15)',
            pointBackgroundColor: '#58a6ff',
          },
        ],
      },
      options: {
        scales: {
          r: {
            min: 0,
            max: 10,
            ticks: {
              stepSize: 2,
              color: '#8b949e',
              backdropColor: 'transparent',
            },
            grid: { color: '#21262d' },
            pointLabels: { color: '#c9d1d9' },
          },
        },
        plugins: { legend: { display: false } },
      },
    });
  }
}
