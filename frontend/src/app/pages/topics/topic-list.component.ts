import { CommonModule } from '@angular/common';
import { Component, inject, Injector, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { NgbModal, NgbModalRef, NgbModalModule } from '@ng-bootstrap/ng-bootstrap';
import { finalize } from 'rxjs';
import { ApiService, Topic } from '../../shared/services/api.service';
import {
  TopicFormModalComponent,
  TOPIC_FORM_MODAL_DATA,
} from './topic-form-modal/topic-form-modal.component';

@Component({
  selector: 'app-topic-list',
  standalone: true,
  imports: [CommonModule, NgbModalModule],
  styleUrls: ['./topic-list.component.scss'],
  templateUrl: './topic-list.component.html',
})
export class TopicListComponent implements OnInit {
  topics = signal<Topic[]>([]);
  loading = signal(false);

  readonly api = inject(ApiService);
  readonly router = inject(Router);
  private readonly injector = inject(Injector);
  private readonly modalService = inject(NgbModal);
  private modalRef: NgbModalRef | null = null;

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
    this.modalRef = this.modalService.open(TopicFormModalComponent, {
      size: 'lg',
      backdrop: 'static',
      keyboard: false,
    });
    this.modalRef.closed.subscribe((created) => {
      this.modalRef = null;
      if (created != null) {
        this.topics.update((list) => [...list, created as Topic]);
      }
    });
    this.modalRef.dismissed.subscribe(() => {
      this.modalRef = null;
    });
  }

  openEditForm(topic: Topic): void {
    const modalInjector = Injector.create({
      providers: [{ provide: TOPIC_FORM_MODAL_DATA, useValue: topic }],
      parent: this.injector,
    });
    this.modalRef = this.modalService.open(TopicFormModalComponent, {
      size: 'lg',
      backdrop: 'static',
      keyboard: false,
      injector: modalInjector,
    });
    this.modalRef.closed.subscribe((updated) => {
      this.modalRef = null;
      if (updated != null) {
        this.topics.update((list) =>
          list.map((t) => (t.id === (updated as Topic).id ? (updated as Topic) : t)),
        );
      }
    });
    this.modalRef.dismissed.subscribe(() => {
      this.modalRef = null;
    });
  }

}
