import { CommonModule } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  ElementRef,
  input,
  model,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

export type ConversationControlsMode = 'voice' | 'chat';

@Component({
  selector: 'app-conversation-controls',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './conversation-controls.component.html',
  styleUrl: './conversation-controls.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConversationControlsComponent {
  vuLevel = input.required<number>();
  recording = input.required<boolean>();
  transcribing = input.required<boolean>();
  aiSpeaking = input.required<boolean>();
  canRecord = input.required<boolean>();
  connected = input.required<boolean>();
  messagesCount = input.required<number>();

  chatInput = model<string>('');

  startRecording = output<void>();
  stopRecording = output<void>();
  sendText = output<void>();

  /** Mobile: show one panel at a time. Desktop CSS shows both. */
  readonly mode = signal<ConversationControlsMode>('voice');
  private readonly chatField = viewChild<ElementRef<HTMLTextAreaElement>>('chatField');

  readonly statusTip = computed(() => {
    if (this.recording()) return { text: 'Recording…', kind: 'recording' as const };
    if (this.transcribing()) return { text: 'Transcribing…', kind: 'transcribing' as const };
    if (this.aiSpeaking()) return { text: 'AI speaking…', kind: 'speaking' as const };
    return { text: 'Hold to speak', kind: 'idle' as const };
  });

  toggleMode(): void {
    this.setMode(this.mode() === 'voice' ? 'chat' : 'voice');
  }

  setMode(next: ConversationControlsMode): void {
    if (this.recording() && next === 'chat') return;
    this.mode.set(next);
    if (next === 'chat') {
      queueMicrotask(() => this.chatField()?.nativeElement.focus());
    }
  }

  /** One pointer path — mouse+touch together fires start/stop twice on Android WebView. */
  onRecordPointerDown(ev: PointerEvent): void {
    if (ev.button !== 0) return;
    (ev.currentTarget as HTMLElement).setPointerCapture(ev.pointerId);
    ev.preventDefault();
    this.startRecording.emit();
  }

  onRecordPointerUp(ev: PointerEvent): void {
    ev.preventDefault();
    this.stopRecording.emit();
  }

  /** Enter sends; Shift+Enter inserts newline. Skips during IME composition. */
  onChatEnterKey(ev: Event): void {
    const ke = ev as KeyboardEvent;
    if (ke.shiftKey || ke.isComposing) return;
    ke.preventDefault();
    this.sendText.emit();
  }
}
