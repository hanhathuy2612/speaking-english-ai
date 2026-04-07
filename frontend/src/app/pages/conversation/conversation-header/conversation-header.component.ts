import { LEVEL_OPTIONS, TTS_RATE_OPTIONS } from '../conversation.constants';
import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { NgOptionTemplateDirective, NgSelectComponent } from '@ng-select/ng-select';

@Component({
  selector: 'app-conversation-header',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, NgSelectComponent, NgOptionTemplateDirective],
  templateUrl: './conversation-header.component.html',
  styleUrl: './conversation-header.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConversationHeaderComponent {
  readonly levelOptions = LEVEL_OPTIONS;
  readonly ttsRateOptions = TTS_RATE_OPTIONS;

  topicTitle = input.required<string>();
  topicId = input.required<number>();
  sessionId = input.required<number>();
  /** Loading session detail before WebSocket (when resuming by id). */
  detailLoading = input(false);
  /** Ended session: read-only transcript, no live chat controls. */
  archiveView = input(false);
  connected = input.required<boolean>();
  reconnecting = input.required<boolean>();
  conversationLevel = input.required<string>();
  ttsRate = input.required<string>();
  ttsVoice = input.required<string>();
  ttsVoices = input.required<{ id: string; name: string }[]>();
  ttsEnabled = input.required<boolean>();
  previewingVoiceId = input.required<string | null>();
  sessionEndedWithFeedback = input.required<boolean>();
  feedbackRequestPending = input.required<boolean>();
  endConversationFeedbackEnabled = input.required<boolean>();

  levelChange = output<string | null>();
  ttsRateChange = output<string>();
  ttsVoiceChange = output<string>();
  toggleTts = output<void>();
  previewVoice = output<string>();
  endFeedback = output<void>();
  newConversationSameTopic = output<void>();

  getVoiceName(voiceId: string): string {
    const v = this.ttsVoices().find((x) => x.id === voiceId);
    return v?.name ?? voiceId ?? 'Select…';
  }
}
