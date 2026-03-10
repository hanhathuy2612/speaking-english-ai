import { Routes } from '@angular/router';
import { authGuard } from './services/auth.guard';

export const routes: Routes = [
  {
    path: 'auth',
    loadChildren: () => import('./auth/auth.routes').then((m) => m.AUTH_ROUTES),
  },
  {
    path: 'topics',
    canActivate: [authGuard],
    loadChildren: () => import('./topics/topics.routes').then((m) => m.TOPIC_ROUTES),
  },
  {
    path: 'conversation',
    canActivate: [authGuard],
    loadChildren: () => import('./conversation/conversation.routes').then((m) => m.CONVERSATION_ROUTES),
  },
  {
    path: 'progress',
    canActivate: [authGuard],
    loadChildren: () => import('./progress/progress.routes').then((m) => m.PROGRESS_ROUTES),
  },
  { path: '', pathMatch: 'full', redirectTo: 'topics' },
  { path: '**', redirectTo: 'topics' },
];
