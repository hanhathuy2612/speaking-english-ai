import { Routes } from '@angular/router';
import { AdminSessionsComponent } from './admin-sessions/admin-sessions.component';
import { AdminTopicsComponent } from './admin-topics/admin-topics.component';
import { AdminTopicEditComponent } from './admin-topics/edit/edit.component';
import { AdminTopicUnitFormPageComponent } from './admin-topics/units/unit-form-page.component';
import { AdminTopicUnitsComponent } from './admin-topics/units/units-list.component';
import { AdminUsersComponent } from './admin-users/admin-users.component';

export const ADMIN_ROUTES: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'users' },
  { path: 'users', component: AdminUsersComponent },
  { path: 'sessions', component: AdminSessionsComponent },
  { path: 'topics', component: AdminTopicsComponent },
  { path: 'topics/:topicId/edit', component: AdminTopicEditComponent },
  { path: 'topics/:topicId/units/new', component: AdminTopicUnitFormPageComponent },
  { path: 'topics/:topicId/units/:unitId/edit', component: AdminTopicUnitFormPageComponent },
  { path: 'topics/:topicId/units', component: AdminTopicUnitsComponent },
];
