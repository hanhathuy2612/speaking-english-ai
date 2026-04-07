import type { TopicUnitWsMeta } from '../model/models';
import { CollapseComponent } from '@/shared/ui';
import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

@Component({
  selector: 'app-conversation-unit-banner',
  standalone: true,
  imports: [CollapseComponent],
  templateUrl: './conversation-unit-banner.component.html',
  styleUrl: './conversation-unit-banner.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConversationUnitBannerComponent {
  step = input.required<TopicUnitWsMeta>();
  collapsed = input.required<boolean>();
  collapsedChange = output<boolean>();
}
