import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal, TemplateRef, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { NgbModal, NgbModalModule } from '@ng-bootstrap/ng-bootstrap';
import { NgSelectComponent } from '@ng-select/ng-select';
import { finalize } from 'rxjs';
import { LEVEL_OPTIONS } from '../../conversation/model/constants';
import {
  ApiService,
  LearningPackOut,
  RoadmapOut,
  RoadmapUnitItem,
  Topic,
} from '../../../shared/services/api.service';
import { LearningPackViewComponent } from '../../../shared/components/learning-pack-view/learning-pack-view.component';
import {
  formatIeltsBand,
  normalizeIeltsLevelInput,
  resolveIeltsBand,
} from '../../../shared/ielts-levels';
@Component({
  selector: 'app-topic-roadmap',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    NgbModalModule,
    FormsModule,
    NgSelectComponent,
    LearningPackViewComponent,
  ],
  styleUrls: ['./topic-roadmap.component.scss'],
  templateUrl: './topic-roadmap.component.html',
})
export class TopicRoadmapComponent implements OnInit {
  @ViewChild('bandModal') bandModalTpl!: TemplateRef<unknown>;

  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(ApiService);
  private readonly modal = inject(NgbModal);

  readonly levelOptions = LEVEL_OPTIONS;

  topicId = signal(0);
  roadmap = signal<RoadmapOut | null>(null);
  topicMeta = signal<Topic | null>(null);
  loading = signal(true);
  actionUnitId = signal<number | null>(null);
  bandDraft = signal('');
  bandSaving = signal(false);
  bandError = signal('');

  topicPack = signal<LearningPackOut | null>(null);
  topicPackLoading = signal(false);
  topicPackError = signal('');
  /** Lazy-loaded per step when the learner opens "Study materials". */
  unitPackById = signal<
    Record<number, { loading: boolean; pack: LearningPackOut | null; error: string }>
  >({});

  readonly topicBandLabel = computed(() => {
    const raw = this.roadmap()?.topic_level ?? this.topicMeta()?.level ?? null;
    const n = resolveIeltsBand(raw);
    if (n != null) {
      return `Band ${formatIeltsBand(n)}`;
    }
    const s = (raw ?? '').trim();
    return s || 'General';
  });

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('topicId'));
    if (!Number.isFinite(id) || id <= 0) {
      this.router.navigate(['/topics']);
      return;
    }
    this.topicId.set(id);
    this.loadRoadmap(id);
    this.api.getTopics().subscribe({
      next: (list) => {
        const t = list.find((x) => x.id === id) ?? null;
        this.topicMeta.set(t);
      },
      error: () => {},
    });
  }

  loadRoadmap(id: number): void {
    this.loading.set(true);
    this.api
      .getTopicRoadmap(id)
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (r) => {
          this.roadmap.set(r);
          this.loadTopicPack(id);
        },
        error: () => this.router.navigate(['/topics']),
      });
  }

  private loadTopicPack(topicId: number): void {
    this.topicPackLoading.set(true);
    this.topicPackError.set('');
    this.api
      .getTopicLearningPack(topicId)
      .pipe(finalize(() => this.topicPackLoading.set(false)))
      .subscribe({
        next: (p) => this.topicPack.set(p),
        error: (err: { error?: { detail?: string } }) => {
          this.topicPack.set(null);
          this.topicPackError.set(err?.error?.detail ?? 'Could not load study materials.');
        },
      });
  }

  unitPackEntry(unitId: number): {
    loading: boolean;
    pack: LearningPackOut | null;
    error: string;
  } {
    return this.unitPackById()[unitId] ?? { loading: false, pack: null, error: '' };
  }

  onUnitDetailsToggle(unitId: number, event: Event): void {
    const el = event.target as HTMLDetailsElement;
    if (!el.open) return;
    const prev = this.unitPackById()[unitId];
    if (prev?.pack != null || prev?.loading) return;
    this.unitPackById.update((m) => ({
      ...m,
      [unitId]: { loading: true, pack: null, error: '' },
    }));
    const tid = this.topicId();
    this.api.getTopicLearningPack(tid, unitId).subscribe({
      next: (p) =>
        this.unitPackById.update((m) => ({
          ...m,
          [unitId]: { loading: false, pack: p, error: '' },
        })),
      error: (err: { error?: { detail?: string } }) =>
        this.unitPackById.update((m) => ({
          ...m,
          [unitId]: {
            loading: false,
            pack: null,
            error: err?.error?.detail ?? 'Could not load materials.',
          },
        })),
    });
  }

  practiceUnit(item: RoadmapUnitItem): void {
    if (item.status === 'locked') return;
    const id = this.topicId();
    const title = this.roadmap()?.topic_title ?? this.topicMeta()?.title ?? 'Conversation';
    this.router.navigate(['/conversation'], {
      queryParams: { topicId: id, title, unitId: item.unit.id },
    });
  }

  freeConversation(): void {
    const id = this.topicId();
    const title = this.roadmap()?.topic_title ?? this.topicMeta()?.title ?? 'Conversation';
    void this.router.navigate(['/conversation'], {
      queryParams: { topicId: id, title },
    });
  }

  markComplete(item: RoadmapUnitItem): void {
    if (item.status !== 'available' && item.status !== 'in_progress') return;
    const tid = this.topicId();
    this.actionUnitId.set(item.unit.id);
    this.api.postRoadmapProgress(tid, item.unit.id).subscribe({
      next: () => this.loadRoadmap(tid),
      error: () => this.actionUnitId.set(null),
      complete: () => this.actionUnitId.set(null),
    });
  }

  statusLabel(status: string): string {
    switch (status) {
      case 'locked':
        return 'Locked';
      case 'available':
        return 'Ready';
      case 'in_progress':
        return 'In progress';
      case 'completed':
        return 'Done';
      default:
        return status;
    }
  }

  openBandModal(): void {
    this.bandError.set('');
    const raw = this.roadmap()?.topic_level ?? this.topicMeta()?.level ?? '';
    this.bandDraft.set(normalizeIeltsLevelInput(raw));
    this.modal.open(this.bandModalTpl, {
      centered: true,
      size: 'md',
      backdrop: 'static',
    });
  }

  saveBand(modal: { close: (result?: unknown) => void }): void {
    const v = this.bandDraft().trim();
    const level = v === '' ? null : normalizeIeltsLevelInput(v);
    this.bandSaving.set(true);
    this.bandError.set('');
    const tid = this.topicId();
    this.api.updateTopic(tid, { level }).subscribe({
      next: (t) => {
        this.topicMeta.set(t);
        this.roadmap.update((r) => (r ? { ...r, topic_level: t.level } : null));
        this.bandSaving.set(false);
        modal.close();
      },
      error: (err: { error?: { detail?: string } }) => {
        this.bandSaving.set(false);
        this.bandError.set(err?.error?.detail ?? 'Could not update band.');
      },
    });
  }
}
