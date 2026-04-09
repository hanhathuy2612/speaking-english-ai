import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, input, model, output } from '@angular/core';
import { FormsModule } from '@angular/forms';

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

  /** Enter sends; Shift+Enter inserts newline. Skips during IME composition. */
  onChatEnterKey(ev: Event): void {
    const ke = ev as KeyboardEvent;
    if (ke.shiftKey || ke.isComposing) return;
    ke.preventDefault();
    this.sendText.emit();
  }
}
