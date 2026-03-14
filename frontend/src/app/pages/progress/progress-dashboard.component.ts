import { ProgressService } from '@/app/shared/services/progress.service';
import { CommonModule } from '@angular/common';
import {
  AfterViewInit,
  Component,
  ElementRef,
  inject,
  OnInit,
  signal,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { ProgressSummary } from '../../shared/services/api.service';

declare const Chart: any;

@Component({
  selector: 'app-progress-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  styleUrls: ['./progress-dashboard.component.scss'],
  templateUrl: './progress-dashboard.component.html',
})
export class ProgressDashboardComponent implements OnInit, AfterViewInit {
  readonly lineChartRef = viewChild<ElementRef<HTMLCanvasElement>>('lineChart');
  readonly radarChartRef = viewChild<ElementRef<HTMLCanvasElement>>('radarChart');

  data = signal<ProgressSummary | undefined>(undefined);
  loading = signal(false);

  readonly progressService = inject(ProgressService);

  ngOnInit(): void {
    this.progressService
      .getProgressSummary()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (d) => {
          this.data.set(d);
        },
        error: () => {
          this.loading.set(false);
        },
      });
  }

  ngAfterViewInit(): void {
    // Chart.js is loaded via CDN in index.html; render once data is available
    const check = setInterval(() => {
      if (this.data() && typeof Chart !== 'undefined') {
        clearInterval(check);
        this._renderCharts();
      }
    }, 200);
  }

  deleteSession(sessionId: number): void {
    this.progressService.deleteSession(sessionId).subscribe({
      next: () => {
        this.data.update((d) =>
          d
            ? { ...d, recent_sessions: d.recent_sessions?.filter((s) => s.id !== sessionId) }
            : undefined,
        );
      },
    });
  }

  private _renderCharts(): void {
    if (!this.data) return;

    // Line chart – daily minutes
    new Chart(this.lineChartRef()?.nativeElement, {
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
    new Chart(this.radarChartRef()?.nativeElement, {
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
