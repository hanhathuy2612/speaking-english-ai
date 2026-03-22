import type { UnitStepSummary } from '@/services/api.service';
import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

@Component({
  selector: 'app-conversation-unit-complete-modal',
  standalone: true,
  templateUrl: './conversation-unit-complete-modal.component.html',
  styleUrl: './conversation-unit-complete-modal.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConversationUnitCompleteModalComponent {
  summary = input.required<UnitStepSummary>();

  roadmap = output<void>();
  stay = output<void>();

  formatAvg(n: number | null | undefined): string {
    if (n == null || Number.isNaN(n)) return '—';
    return n.toFixed(1);
  }
}
