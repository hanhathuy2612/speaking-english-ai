import { environment } from '@/environments/environment';
import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

export interface Topic {
  id: number;
  title: string;
  description: string | null;
  level: string | null;
}

export interface TopicUnitDto {
  id: number;
  topic_id: number;
  sort_order: number;
  title: string;
  objective: string;
  prompt_hint: string;
  min_turns_to_complete: number | null;
  min_avg_overall: number | null;
}

export interface RoadmapUnitItem {
  unit: TopicUnitDto;
  status: 'locked' | 'available' | 'in_progress' | 'completed';
}

export interface RoadmapOut {
  topic_id: number;
  topic_title: string;
  units: RoadmapUnitItem[];
}

export interface RoadmapProgressOut {
  ok: boolean;
  topic_unit_id: number;
  completed_at: string | null;
}

export interface ProgressSummary {
  total_sessions: number;
  total_turns: number;
  avg_scores: { fluency: number; vocabulary: number; grammar: number; overall: number } | null;
  daily_minutes: { date: string; minutes: number }[];
}

export interface TtsVoice {
  id: string;
  name: string;
  gender: string;
  locale: string;
}

export interface GuidanceResponse {
  suggestions: string[];
}

export interface AdminUserOut {
  id: number;
  email: string;
  username: string;
  is_active: boolean;
  roles: string[];
  created_at: string;
}

export interface AdminUserListOut {
  items: AdminUserOut[];
  total: number;
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

  getTopicRoadmap(topicId: number): Observable<RoadmapOut> {
    return this.http.get<RoadmapOut>(`${this.base}/topics/${topicId}/roadmap`);
  }

  /** Mark a roadmap step complete (unlock next step). */
  postRoadmapProgress(topicId: number, topicUnitId: number): Observable<RoadmapProgressOut> {
    return this.http.post<RoadmapProgressOut>(`${this.base}/topics/${topicId}/roadmap/progress`, {
      topic_unit_id: topicUnitId,
      action: 'complete',
    });
  }

  /** List TTS voices for dropdown (id, name, gender, locale). */
  getTtsVoices(): Observable<TtsVoice[]> {
    return this.http.get<TtsVoice[]>(`${this.base}/tts/voices`);
  }

  /** Short TTS sample for a voice (to try before selecting). */
  getTtsPreview(voiceId: string, rate: string): Observable<Blob> {
    const params = new URLSearchParams({ voice: voiceId, rate });
    return this.http.get(`${this.base}/tts/preview?${params}`, {
      responseType: 'blob',
    });
  }

  /** Get answer suggestions for a question (for the guide panel). Optionally pass turnId to save guideline to that turn. */
  getGuidance(question: string, turnId?: number): Observable<GuidanceResponse> {
    const body: { question: string; turn_id?: number } = { question: question.trim() };
    if (turnId != null) body.turn_id = turnId;
    return this.http.post<GuidanceResponse>(`${this.base}/conversation/guidance`, body);
  }

  adminListUsers(page: number, limit: number): Observable<AdminUserListOut> {
    const q = new URLSearchParams({
      page: String(page),
      limit: String(limit),
    });
    return this.http.get<AdminUserListOut>(`${this.base}/admin/users?${q}`);
  }

  adminPatchUser(
    userId: number,
    body: { is_active?: boolean; role_slugs?: string[] },
  ): Observable<AdminUserOut> {
    return this.http.patch<AdminUserOut>(`${this.base}/admin/users/${userId}`, body);
  }

  adminCreateTopicUnit(
    topicId: number,
    body: {
      sort_order: number;
      title: string;
      objective: string;
      prompt_hint: string;
      min_turns_to_complete?: number | null;
      min_avg_overall?: number | null;
    },
  ): Observable<TopicUnitDto> {
    return this.http.post<TopicUnitDto>(`${this.base}/admin/topics/${topicId}/units`, body);
  }
}
