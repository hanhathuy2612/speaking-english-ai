import { Routes } from '@angular/router';
import { TopicListComponent } from './topic-list.component';
import { TopicRoadmapComponent } from './topic-roadmap/topic-roadmap.component';

export const TOPIC_ROUTES: Routes = [
  { path: '', component: TopicListComponent },
  { path: ':topicId/roadmap', component: TopicRoadmapComponent },
];
