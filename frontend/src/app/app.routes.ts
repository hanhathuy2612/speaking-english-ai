import { Routes } from '@angular/router';
import { adminGuard } from './shared/services/admin.guard';
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
  {
    path: 'admin',
    canActivate: [authGuard, adminGuard],
    loadChildren: () => import('./pages/admin/admin.routes').then((m) => m.ADMIN_ROUTES),
  },
  { path: '', pathMatch: 'full', redirectTo: 'topics' },
  { path: '**', redirectTo: 'topics' },
];
