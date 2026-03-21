import { Routes } from '@angular/router';
import { AdminUsersComponent } from './admin-users/admin-users.component';

export const ADMIN_ROUTES: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'users' },
  { path: 'users', component: AdminUsersComponent },
];
