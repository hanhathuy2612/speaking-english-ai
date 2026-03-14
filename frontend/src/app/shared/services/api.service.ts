import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
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
  recent_sessions: {
    id: number;
    topic_title: string;
    started_at: string;
    ended_at: string | null;
    turn_count: number;
    avg_overall: number | null;
  }[];
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly base = environment.apiBaseUrl;

  constructor(private http: HttpClient) {}

  getTopics(): Observable<Topic[]> {
    return this.http.get<Topic[]>(`${this.base}/topics`);
  }

  getProgressSummary(): Observable<ProgressSummary> {
    return this.http.get<ProgressSummary>(`${this.base}/progress/summary`);
  }
}
