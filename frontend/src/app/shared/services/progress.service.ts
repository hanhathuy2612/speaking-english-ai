import { environment } from '@/environments/environment';
import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ProgressSummary } from './api.service';

export interface RecentSessionItem {
  id: number;
  topic_id: number;
  topic_title: string;
  started_at: string;
  ended_at: string | null;
  turn_count: number;
  avg_overall: number | null;
}

export interface SessionsPageResponse {
  items: RecentSessionItem[];
  total: number;
}

@Injectable({ providedIn: 'root' })
export class ProgressService {
  private readonly base = environment.apiBaseUrl;
  private readonly http = inject(HttpClient);

  getProgressSummary(): Observable<ProgressSummary> {
    return this.http.get<ProgressSummary>(`${this.base}/progress/summary`);
  }

  getSessions(page: number, limit: number): Observable<SessionsPageResponse> {
    const params = { page: String(page), limit: String(limit) };
    return this.http.get<SessionsPageResponse>(`${this.base}/progress/sessions`, {
      params,
    });
  }

  /** All sessions for one topic (paginated). */
  getTopicSessions(topicId: number, page: number, limit: number): Observable<SessionsPageResponse> {
    const params = { page: String(page), limit: String(limit) };
    return this.http.get<SessionsPageResponse>(`${this.base}/topics/${topicId}/sessions`, {
      params,
    });
  }

  deleteSession(sessionId: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/progress/sessions/${sessionId}`);
  }
}
