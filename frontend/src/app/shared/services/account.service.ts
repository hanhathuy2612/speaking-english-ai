import { environment } from '@/environments/environment';
import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

export interface IUserSettings {
  user_id: number;
  username: string;
  tts_voice: string | null;
  tts_rate: string | null;
}

@Injectable({ providedIn: 'root' })
export class AccountService {
  private readonly base = environment.apiBaseUrl;
  private readonly http = inject(HttpClient);

  /** Current user profile and saved TTS preferences. */
  getMe(): Observable<IUserSettings> {
    return this.http.get<IUserSettings>(`${this.base}/users/me`);
  }

  /** Update current user TTS preferences. */
  patchMe(prefs: Partial<IUserSettings>): Observable<IUserSettings> {
    return this.http.patch<IUserSettings>(`${this.base}/users/me`, prefs);
  }
}
