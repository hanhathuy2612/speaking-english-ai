import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, finalize, shareReplay, tap, throwError } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AccountService } from './account.service';

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user_id: number;
  username: string;
  roles: string[];
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly base = environment.apiBaseUrl;
  private refreshInFlight$: Observable<AuthResponse> | null = null;

  constructor(
    private http: HttpClient,
    private router: Router,
    private account: AccountService,
  ) {}

  register(email: string, username: string, password: string): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${this.base}/auth/register`, { email, username, password })
      .pipe(
        tap((r: AuthResponse) => {
          this._store(r);
          this.account.applyLoginResponse(r);
        }),
      );
  }

  login(email: string, password: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.base}/auth/login`, { email, password }).pipe(
      tap((r: AuthResponse) => {
        this._store(r);
        this.account.applyLoginResponse(r);
      }),
    );
  }

  logout(): void {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('username');
    this.account.clearProfile();
    this.router.navigateByUrl('/auth/login');
  }

  getToken(): string | null {
    return localStorage.getItem('token');
  }

  getUsername(): string | null {
    return localStorage.getItem('username');
  }

  isLoggedIn(): boolean {
    return !!this.getToken();
  }

  refreshAccessToken(): Observable<AuthResponse> {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
      return throwError(() => new Error('No refresh token'));
    }
    if (!this.refreshInFlight$) {
      this.refreshInFlight$ = this.http
        .post<AuthResponse>(`${this.base}/auth/refresh`, { refresh_token: refreshToken })
        .pipe(
          tap((r: AuthResponse) => {
            this._store(r);
            this.account.applyLoginResponse(r);
          }),
          finalize(() => {
            this.refreshInFlight$ = null;
          }),
          shareReplay(1),
        );
    }
    return this.refreshInFlight$;
  }

  private _store(r: AuthResponse): void {
    localStorage.setItem('token', r.access_token);
    localStorage.setItem('refresh_token', r.refresh_token);
    localStorage.setItem('username', r.username);
  }
}
