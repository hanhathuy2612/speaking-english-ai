import { environment } from '@/environments/environment';
import { HttpClient } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';

export interface IUserProfile {
  user_id: number;
  email: string;
  username: string;
  roles: string[];
  tts_voice: string | null;
  tts_rate: string | null;
}

@Injectable({ providedIn: 'root' })
export class AccountService {
  private readonly base = environment.apiBaseUrl;
  private readonly http = inject(HttpClient);

  /** Cached profile; null when logged out or not loaded yet. */
  readonly profile = signal<IUserProfile | null>(null);

  readonly isAdmin = computed(() => (this.profile()?.roles ?? []).includes('admin'));

  hasRole(slug: string): boolean {
    return (this.profile()?.roles ?? []).includes(slug);
  }

  clearProfile(): void {
    this.profile.set(null);
  }

  /** After login/register: set roles from token response, then hydrate from /me. */
  applyLoginResponse(r: { user_id: number; username: string; roles: string[] }): void {
    this.profile.set({
      user_id: r.user_id,
      username: r.username,
      email: '',
      roles: r.roles ?? [],
      tts_voice: null,
      tts_rate: null,
    });
    this.getMe().subscribe({
      next: (me) => this.profile.set(me),
      error: () => {},
    });
  }

  /** Load profile when app starts with an existing token. */
  refreshFromServer(): Observable<IUserProfile> {
    return this.getMe().pipe(tap((me) => this.profile.set(me)));
  }

  getMe(): Observable<IUserProfile> {
    return this.http
      .get<IUserProfile>(`${this.base}/users/me`)
      .pipe(tap((me) => this.profile.set(me)));
  }

  patchMe(prefs: Partial<IUserProfile>): Observable<IUserProfile> {
    return this.http
      .patch<IUserProfile>(`${this.base}/users/me`, prefs)
      .pipe(tap((me) => this.profile.set(me)));
  }
}
