import { CommonModule } from '@angular/common';
import { Component, inject, Injector, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { NgbModal, NgbModalModule } from '@ng-bootstrap/ng-bootstrap';
import { finalize } from 'rxjs';
import { AccountService } from '../../../shared/services/account.service';
import {
  ApiService,
  RoadmapOut,
  RoadmapUnitItem,
  Topic,
} from '../../../shared/services/api.service';
import {
  TOPIC_UNIT_FORM_MODAL_DATA,
  TopicUnitFormModalComponent,
} from '../topic-unit-form-modal/topic-unit-form-modal.component';

@Component({
  selector: 'app-topic-roadmap',
  standalone: true,
  imports: [CommonModule, RouterLink, NgbModalModule],
  styleUrls: ['./topic-roadmap.component.scss'],
  templateUrl: './topic-roadmap.component.html',
})
export class TopicRoadmapComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(ApiService);
  private readonly modal = inject(NgbModal);
  private readonly injector = inject(Injector);
  readonly account = inject(AccountService);

  topicId = signal(0);
  roadmap = signal<RoadmapOut | null>(null);
  topicMeta = signal<Topic | null>(null);
  loading = signal(true);
  actionUnitId = signal<number | null>(null);

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
        next: (r) => this.roadmap.set(r),
        error: () => this.router.navigate(['/topics']),
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

  suggestedNextSortOrder(): number {
    const u = this.roadmap()?.units ?? [];
    if (!u.length) return 1;
    return Math.max(...u.map((x) => x.unit.sort_order), 0) + 1;
  }

  openCreateUnitModal(): void {
    const topicId = this.topicId();
    const inj = Injector.create({
      providers: [
        {
          provide: TOPIC_UNIT_FORM_MODAL_DATA,
          useValue: {
            topicId,
            suggestedSortOrder: this.suggestedNextSortOrder(),
          },
        },
      ],
      parent: this.injector,
    });
    const ref = this.modal.open(TopicUnitFormModalComponent, {
      size: 'lg',
      backdrop: 'static',
      keyboard: false,
      injector: inj,
    });
    ref.closed.subscribe((created: unknown) => {
      if (created != null) this.loadRoadmap(topicId);
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
}
