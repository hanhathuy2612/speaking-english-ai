import { ApiService, Topic } from '@/app/shared/services/api.service';
import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

const FREE_CONVERSATION_TOPIC_TITLE = 'Free Conversation';
const FREE_CONVERSATION_TOPIC_DESCRIPTION =
  'Internal topic for open-ended conversation mode (chat or voice).';
const FREE_CONVERSATION_TOPIC_LEVEL = '6';

@Component({
  selector: 'app-free-conversation-page',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './free-chat-page.component.html',
  styleUrls: ['./free-chat-page.component.scss'],
})
export class FreeChatPageComponent {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  readonly creatingSession = signal(false);
  readonly errorMessage = signal('');

  async startFreeConversation(): Promise<void> {
    if (this.creatingSession()) return;
    this.errorMessage.set('');
    this.creatingSession.set(true);

    try {
      const freeTopic = await this._findOrCreateFreeConversationTopic();
      const createdSession = await firstValueFrom(
        this.api.postCreateSession({
          topic_id: freeTopic.id,
          topic_unit_id: null,
        }),
      );

      await this.router.navigate(['/conversation'], {
        queryParams: {
          topicId: freeTopic.id,
          title: freeTopic.title,
          sessionId: createdSession.id,
        },
      });
    } catch {
      this.errorMessage.set(
        'Không thể bắt đầu Free Conversation lúc này. Bạn thử lại sau vài giây nhé.',
      );
    } finally {
      this.creatingSession.set(false);
    }
  }

  private async _findOrCreateFreeConversationTopic(): Promise<Topic> {
    const topics = await firstValueFrom(this.api.getTopics());
    const found = topics.find(
      (topic) => topic.title.trim().toLowerCase() === FREE_CONVERSATION_TOPIC_TITLE.toLowerCase(),
    );
    if (found) return found;

    return await firstValueFrom(
      this.api.createTopic({
        title: FREE_CONVERSATION_TOPIC_TITLE,
        description: FREE_CONVERSATION_TOPIC_DESCRIPTION,
        level: FREE_CONVERSATION_TOPIC_LEVEL,
      }),
    );
  }
}
