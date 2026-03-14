import { environment } from '@/environments/environment';
import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { ProgressSummary } from './api.service';
import { Observable } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class ProgressService {
  private readonly base = environment.apiBaseUrl;

  constructor(private http: HttpClient) {}

  getProgressSummary(): Observable<ProgressSummary> {
    return this.http.get<ProgressSummary>(`${this.base}/progress/summary`);
  }

  deleteSession(sessionId: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/progress/sessions/${sessionId}`);
  }
}
