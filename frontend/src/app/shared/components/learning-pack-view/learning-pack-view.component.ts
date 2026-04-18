import { CommonModule } from '@angular/common';
import { Component, input } from '@angular/core';
import {
  isLearningPackEmpty,
  type LearningPackOut,
} from '@/shared/models/learning-pack.model';

@Component({
  selector: 'app-learning-pack-view',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './learning-pack-view.component.html',
  styleUrl: './learning-pack-view.component.scss',
})
export class LearningPackViewComponent {
  readonly pack = input<LearningPackOut | null>(null);
  readonly loading = input(false);
  readonly error = input('');

  protected readonly isEmpty = isLearningPackEmpty;

  protected sourceLabel(source: string | null | undefined): string {
    switch (source) {
      case 'unit':
        return 'Step-specific';
      case 'topic':
        return 'Topic';
      case 'fallback':
        return 'Suggested';
      default:
        return '';
    }
  }
}
