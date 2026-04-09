import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { MarkdownHtmlPipe } from '../../../shared/pipes/markdown-html.pipe';
import { decodeEscapedLineBreaks } from '../../../shared/utils/chat-text';

@Component({
  selector: 'app-conversation-guide-panel',
  standalone: true,
  imports: [MarkdownHtmlPipe],
  templateUrl: './conversation-guide-panel.component.html',
  styleUrl: './conversation-guide-panel.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConversationGuidePanelComponent {
  displaySourceText(text: string): string {
    return decodeEscapedLineBreaks(text);
  }

  panelTitle = input('Tips');
  sourceLabel = input('Question');
  tipsLabel = input('Gợi ý trả lời');
  sourceText = input.required<string>();
  suggestions = input.required<string[]>();
  loading = input.required<boolean>();
  panelWidthPx = input.required<number>();
  sidebarDesktop = input.required<boolean>();

  closeRequested = output<void>();
  refreshRequested = output<void>();
  resizePointerDown = output<PointerEvent>();
}
