import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const token = auth.getToken();
  const isRefreshCall = req.url.includes('/auth/refresh');
  const isPublicAuthCall = req.url.includes('/auth/login') || req.url.includes('/auth/register');

  if (token && !isRefreshCall) {
    req = req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
  }

  return next(req).pipe(
    catchError((error: unknown) => {
      if (
        !(error instanceof HttpErrorResponse) ||
        error.status !== 401 ||
        isRefreshCall ||
        isPublicAuthCall
      ) {
        return throwError(() => error);
      }

      return auth.refreshAccessToken().pipe(
        switchMap((res) => {
          const retryReq = req.clone({
            setHeaders: { Authorization: `Bearer ${res.access_token}` },
          });
          return next(retryReq);
        }),
        catchError((refreshError: unknown) => {
          auth.logout();
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
