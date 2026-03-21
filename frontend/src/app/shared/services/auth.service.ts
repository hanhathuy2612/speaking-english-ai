import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AccountService } from './account.service';

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  username: string;
  roles: string[];
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly base = environment.apiBaseUrl;

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
    return this.http
      .post<AuthResponse>(`${this.base}/auth/login`, { email, password })
      .pipe(
        tap((r: AuthResponse) => {
          this._store(r);
          this.account.applyLoginResponse(r);
        }),
      );
  }

  logout(): void {
    localStorage.removeItem('token');
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

  private _store(r: AuthResponse): void {
    localStorage.setItem('token', r.access_token);
    localStorage.setItem('username', r.username);
  }
}
