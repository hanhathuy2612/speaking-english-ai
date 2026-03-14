import { Routes } from '@angular/router';
import { authGuard } from './shared/services/auth.guard';

export const routes: Routes = [
  {
    path: 'auth',
    loadChildren: () => import('./pages/auth/auth.routes').then((m) => m.AUTH_ROUTES),
  },
  {
    path: 'topics',
    canActivate: [authGuard],
    loadChildren: () => import('./pages/topics/topics.routes').then((m) => m.TOPIC_ROUTES),
  },
  {
    path: 'conversation',
    canActivate: [authGuard],
    loadChildren: () =>
      import('./pages/conversation/conversation.routes').then((m) => m.CONVERSATION_ROUTES),
  },
  {
    path: 'progress',
    canActivate: [authGuard],
    loadChildren: () => import('./pages/progress/progress.routes').then((m) => m.PROGRESS_ROUTES),
  },
  { path: '', pathMatch: 'full', redirectTo: 'topics' },
  { path: '**', redirectTo: 'topics' },
];
