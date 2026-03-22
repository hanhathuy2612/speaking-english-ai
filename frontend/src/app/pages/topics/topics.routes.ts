import { Routes } from '@angular/router';
import { TopicListComponent } from './topic-list.component';
import { TopicRoadmapComponent } from './topic-roadmap/topic-roadmap.component';
import { TopicSessionHistoryComponent } from './topic-session-history/topic-session-history.component';

export const TOPIC_ROUTES: Routes = [
  { path: '', component: TopicListComponent },
  { path: ':topicId/sessions', component: TopicSessionHistoryComponent },
  { path: ':topicId/roadmap', component: TopicRoadmapComponent },
];
