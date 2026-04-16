import type { ChatMessage } from '../model/models';
import { CommonModule } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  effect,
  ElementRef,
  inject,
  input,
  output,
  viewChild,
} from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { marked } from 'marked';
import { decodeEscapedLineBreaks } from '../../../shared/utils/chat-text';

marked.setOptions({ gfm: true, breaks: true });

@Component({
  selector: 'app-conversation-message-list',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './conversation-message-list.component.html',
  styleUrl: './conversation-message-list.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConversationMessageListComponent {
  private readonly sanitizer = inject(DomSanitizer);

  messages = input.required<ChatMessage[]>();
  connected = input.required<boolean>();
  transcribing = input.required<boolean>();
  playingMessageIndex = input.required<number>();
  reworkAllowed = input.required<boolean>();

  guideOpen = output<{ message: ChatMessage; index: number }>();
  optimizeOpen = output<{ message: ChatMessage; index: number }>();
  rework = output<number>();
  playAudio = output<{ msg: ChatMessage; index: number; kind: 'user' | 'ai' }>();

  private readonly chatArea = viewChild<ElementRef<HTMLDivElement>>('chatArea');

  constructor() {
    effect(() => {
      this.messages();
      this.transcribing();
      requestAnimationFrame(() => this._scrollToBottom());
    });
  }

  /** Public hook if parent needs to force scroll (e.g. future header action). */
  scrollToBottom(): void {
    this._scrollToBottom(true);
  }

  private _isNearBottom(): boolean {
    const el = this.chatArea()?.nativeElement;
    if (!el) return true;
    const threshold = 150;
    return el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
  }

  private _scrollToBottom(force = false): void {
    try {
      const el = this.chatArea()?.nativeElement;
      if (!el) return;
      if (!force && !this._isNearBottom()) return;
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    } catch {
      /* ignore */
    }
  }

  renderMarkdown(text: string | null | undefined): SafeHtml {
    const raw = decodeEscapedLineBreaks(text ?? '').trim();
    if (!raw) return this.sanitizer.bypassSecurityTrustHtml('');
    const html = marked(raw, { async: false });
    return this.sanitizer.bypassSecurityTrustHtml(html);
  }

  /** Plain bubble text: decode literal \\n so it matches real line breaks in the textarea. */
  plainChatText(text: string | null | undefined, trim: boolean): string {
    const d = decodeEscapedLineBreaks(text ?? '');
    return trim ? d.trim() : d;
  }
}
