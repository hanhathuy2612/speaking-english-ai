import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { AccountService } from './account.service';

export const adminGuard: CanActivateFn = () => {
  const account = inject(AccountService);
  const router = inject(Router);
  const p = account.profile();
  if (p != null) {
    return p.roles.includes('admin') ? true : router.parseUrl('/topics');
  }
  return account.refreshFromServer().pipe(
    map((me) => (me.roles.includes('admin') ? true : router.parseUrl('/topics'))),
    catchError(() => of(router.parseUrl('/topics'))),
  );
};
