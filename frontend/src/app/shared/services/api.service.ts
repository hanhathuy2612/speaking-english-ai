import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface Topic {
  id: number;
  title: string;
  description: string | null;
  level: string | null;
}

export interface ProgressSummary {
  total_sessions: number;
  total_turns: number;
  avg_scores: { fluency: number; vocabulary: number; grammar: number; overall: number } | null;
  daily_minutes: { date: string; minutes: number }[];
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly base = environment.apiBaseUrl;

  constructor(private http: HttpClient) {}

  getTopics(): Observable<Topic[]> {
    return this.http.get<Topic[]>(`${this.base}/topics`);
  }

  /** Create a new topic (saved to database). */
  createTopic(payload: {
    title: string;
    description?: string | null;
    level?: string | null;
  }): Observable<Topic> {
    return this.http.post<Topic>(`${this.base}/topics`, payload);
  }

  /** Update an existing topic. */
  updateTopic(
    id: number,
    payload: { title?: string; description?: string | null; level?: string | null },
  ): Observable<Topic> {
    return this.http.patch<Topic>(`${this.base}/topics/${id}`, payload);
  }

  /** List TTS voices for dropdown (id, name, gender, locale). */
  getTtsVoices(): Observable<{ id: string; name: string; gender: string; locale: string }[]> {
    return this.http.get<{ id: string; name: string; gender: string; locale: string }[]>(
      `${this.base}/tts/voices`,
    );
  }

  /** Short TTS sample for a voice (to try before selecting). */
  getTtsPreview(voiceId: string, rate: string): Observable<Blob> {
    const params = new URLSearchParams({ voice: voiceId, rate });
    return this.http.get(`${this.base}/tts/preview?${params}`, {
      responseType: 'blob',
    });
  }

  /** Current user profile and saved TTS preferences. */
  getMe(): Observable<{
    user_id: number;
    username: string;
    tts_voice: string | null;
    tts_rate: string | null;
  }> {
    return this.http.get<{
      user_id: number;
      username: string;
      tts_voice: string | null;
      tts_rate: string | null;
    }>(`${this.base}/users/me`);
  }

  /** Update current user TTS preferences. */
  patchMe(prefs: {
    tts_voice?: string;
    tts_rate?: string;
  }): Observable<{ tts_voice: string | null; tts_rate: string | null }> {
    return this.http.patch<{ tts_voice: string | null; tts_rate: string | null }>(
      `${this.base}/users/me`,
      prefs,
    );
  }

  /** Get answer suggestions for a question (for the guide panel). Optionally pass turnId to save guideline to that turn. */
  getGuidance(question: string, turnId?: number): Observable<{ suggestions: string[] }> {
    const body: { question: string; turn_id?: number } = { question: question.trim() };
    if (turnId != null) body.turn_id = turnId;
    return this.http.post<{ suggestions: string[] }>(`${this.base}/conversation/guidance`, body);
  }
}
