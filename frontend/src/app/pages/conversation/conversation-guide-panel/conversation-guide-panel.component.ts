import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

@Component({
  selector: 'app-conversation-guide-panel',
  standalone: true,
  templateUrl: './conversation-guide-panel.component.html',
  styleUrl: './conversation-guide-panel.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConversationGuidePanelComponent {
  questionText = input.required<string>();
  suggestions = input.required<string[]>();
  loading = input.required<boolean>();
  panelWidthPx = input.required<number>();
  sidebarDesktop = input.required<boolean>();

  close = output<void>();
  resizePointerDown = output<PointerEvent>();
}
