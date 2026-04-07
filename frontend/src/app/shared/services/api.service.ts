import { environment } from '@/environments/environment';
import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

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
  max_scored_turns: number | null;
}

export interface UnitStepSummary {
  session_id: number;
  topic_id: number;
  topic_title: string;
  topic_unit: { id: number; title: string; objective: string } | null;
  scored_turns: number;
  avg_fluency: number | null;
  avg_vocabulary: number | null;
  avg_grammar: number | null;
  avg_overall: number | null;
  min_turns_to_complete: number | null;
  min_avg_overall: number | null;
  max_scored_turns: number | null;
  thresholds_met: boolean;
}

export interface RoadmapUnitItem {
  unit: TopicUnitDto;
  status: 'locked' | 'available' | 'in_progress' | 'completed';
}

export interface RoadmapOut {
  topic_id: number;
  topic_title: string;
  topic_level: string | null;
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

export interface SessionEndScoreTurn {
  turnId: number;
  fluency: number;
  vocabulary: number;
  grammar: number;
  overall: number;
  feedback: string;
}

/** POST .../conversation/sessions/{id}/end — same scoring payload shape as WebSocket session_scores. */
export interface SessionDetailTurn {
  turn_id: number;
  /** DB id of the user message row (voice recording); use for user audio fetch. */
  user_message_id: number;
  index_in_session: number;
  user_text: string;
  assistant_text: string;
  has_user_audio?: boolean;
  has_assistant_audio?: boolean;
  guideline?: string | null;
  fluency?: number | null;
  vocabulary?: number | null;
  grammar?: number | null;
  overall?: number | null;
  feedback?: string | null;
  created_at: string;
}

export interface SessionDetailOut {
  id: number;
  topic_id: number;
  topic_title: string;
  started_at: string;
  ended_at: string | null;
  opening_message?: string | null;
  has_opening_audio?: boolean;
  turns: SessionDetailTurn[];
  session_feedback?: string | null;
}

export interface SessionCreatePayload {
  topic_id: number;
  topic_unit_id?: number | null;
}

export interface SessionCreatedOut {
  id: number;
  topic_id: number;
  topic_unit_id: number | null;
  topic_level: string | null;
}

export interface SessionEndScoresResponse {
  turns: SessionEndScoreTurn[];
  averages: {
    fluency: number;
    vocabulary: number;
    grammar: number;
    overall: number;
  } | null;
  /** One Vietnamese tutor recap: scores, mistakes, how to improve (not per-turn). */
  session_feedback: string;
  roadmap_unit_completed: boolean;
  topic_unit_id: number | null;
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

/** Admin: all users' sessions on one topic. */
export interface AdminTopicSessionItem {
  id: number;
  topic_id: number;
  topic_title: string;
  user_id: number;
  user_email: string;
  user_username: string;
  topic_unit_title: string | null;
  started_at: string;
  ended_at: string | null;
  turn_count: number;
  avg_overall: number | null;
}

export interface AdminTopicSessionsPage {
  items: AdminTopicSessionItem[];
  total: number;
}

export interface AITopicDraftOut {
  title: string;
  description: string | null;
  level: string | null;
}

export interface AITopicUnitDraftOut {
  title: string;
  objective: string;
  prompt_hint: string;
  min_turns_to_complete: number | null;
  min_avg_overall: number | null;
  max_scored_turns: number | null;
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

  /** Get answer suggestions for a question (for the guide panel). Optionally pass messageId to save guideline. */
  getGuidance(
    question: string,
    messageId?: number,
    level?: string | null,
  ): Observable<GuidanceResponse> {
    const body: { question: string; message_id?: number; level?: string } = {
      question: question.trim(),
    };
    if (messageId != null) body.message_id = messageId;
    const lv = (level ?? '').trim();
    if (lv !== '') body.level = lv;
    return this.http.post<GuidanceResponse>(`${this.base}/conversation/guidance`, body);
  }

  /** Persist guide text on a message (used when guideline was generated before message id existed). */
  patchMessageGuideline(messageId: number, guideline: string): Observable<{ ok: boolean }> {
    return this.http.patch<{ ok: boolean }>(
      `${this.base}/conversation/messages/${messageId}/guideline`,
      {
        guideline,
      },
    );
  }

  /** Full session transcript + scores (for archive / detail view). */
  getSessionDetail(sessionId: number): Observable<SessionDetailOut> {
    return this.http.get<SessionDetailOut>(`${this.base}/conversation/sessions/${sessionId}`);
  }

  /** Create an empty session (then navigate to /conversation?sessionId=…). */
  postCreateSession(body: SessionCreatePayload): Observable<SessionCreatedOut> {
    return this.http.post<SessionCreatedOut>(`${this.base}/conversation/sessions`, body);
  }

  /** Learner webm or assistant TTS mp3 for a message (requires auth). */
  getMessageAudio(messageId: number, kind: 'user' | 'assistant'): Observable<ArrayBuffer> {
    return this.http.get(`${this.base}/conversation/messages/${messageId}/audio`, {
      params: { kind },
      responseType: 'arraybuffer',
    });
  }

  getSessionOpeningAudio(sessionId: number): Observable<ArrayBuffer> {
    return this.http.get(`${this.base}/conversation/sessions/${sessionId}/opening-audio`, {
      responseType: 'arraybuffer',
    });
  }

  /** Session aggregates for roadmap unit completion / recap. */
  getUnitStepSummary(sessionId: number): Observable<UnitStepSummary> {
    return this.http.get<UnitStepSummary>(
      `${this.base}/conversation/sessions/${sessionId}/unit-step-summary`,
    );
  }

  /** End session, score turns, set ended_at (call after WebSocket is closed). */
  postSessionEnd(sessionId: number): Observable<SessionEndScoresResponse> {
    return this.http.post<SessionEndScoresResponse>(
      `${this.base}/conversation/sessions/${sessionId}/end`,
      {},
    );
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
      max_scored_turns?: number | null;
    },
  ): Observable<TopicUnitDto> {
    return this.http.post<TopicUnitDto>(`${this.base}/admin/topics/${topicId}/units`, body);
  }

  adminUpdateTopicUnit(
    topicId: number,
    unitId: number,
    body: {
      sort_order?: number;
      title?: string;
      objective?: string;
      prompt_hint?: string;
      min_turns_to_complete?: number | null;
      min_avg_overall?: number | null;
      max_scored_turns?: number | null;
    },
  ): Observable<TopicUnitDto> {
    return this.http.patch<TopicUnitDto>(
      `${this.base}/admin/topics/${topicId}/units/${unitId}`,
      body,
    );
  }

  adminDeleteTopicUnit(topicId: number, unitId: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/admin/topics/${topicId}/units/${unitId}`);
  }

  adminDeleteTopic(topicId: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/admin/topics/${topicId}`);
  }

  adminListTopicSessions(
    topicId: number,
    page: number,
    limit: number,
    topicUnitId?: number | null,
  ): Observable<AdminTopicSessionsPage> {
    const q = new URLSearchParams({
      page: String(page),
      limit: String(limit),
    });
    if (topicUnitId != null && topicUnitId > 0) {
      q.set('topic_unit_id', String(topicUnitId));
    }
    return this.http.get<AdminTopicSessionsPage>(
      `${this.base}/admin/topics/${topicId}/sessions?${q}`,
    );
  }

  /** Admin: all sessions, optional filters by user and/or topic. */
  adminListAllSessions(
    page: number,
    limit: number,
    filters?: { userId?: number | null; topicId?: number | null },
  ): Observable<AdminTopicSessionsPage> {
    const q = new URLSearchParams({
      page: String(page),
      limit: String(limit),
    });
    if (filters?.userId != null && filters.userId > 0) {
      q.set('user_id', String(filters.userId));
    }
    if (filters?.topicId != null && filters.topicId > 0) {
      q.set('topic_id', String(filters.topicId));
    }
    return this.http.get<AdminTopicSessionsPage>(`${this.base}/admin/sessions?${q}`);
  }

  adminDeleteTopicSession(topicId: number, sessionId: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/admin/topics/${topicId}/sessions/${sessionId}`);
  }

  adminGenerateTopicDraft(idea?: string | null): Observable<AITopicDraftOut> {
    return this.http
      .post<Record<string, unknown>>(`${this.base}/admin/ai/topic-draft`, {
        idea: (idea ?? '').trim() || null,
      })
      .pipe(map((raw) => this.normalizeAiTopicDraft(raw)));
  }

  adminGenerateTopicUnitDraft(
    topicId: number,
    idea?: string | null,
  ): Observable<AITopicUnitDraftOut> {
    return this.http
      .post<Record<string, unknown>>(`${this.base}/admin/ai/topics/${topicId}/unit-draft`, {
        idea: (idea ?? '').trim() || null,
      })
      .pipe(map((raw) => this.normalizeAiTopicUnitDraft(raw)));
  }

  private normalizeAiTopicDraft(raw: Record<string, unknown>): AITopicDraftOut {
    return {
      title: String(raw['title'] ?? '').trim(),
      description: this.asNullableString(raw['description'] ?? raw['desc']),
      level: this.asNullableString(raw['level']),
    };
  }

  private normalizeAiTopicUnitDraft(raw: Record<string, unknown>): AITopicUnitDraftOut {
    return {
      title: String(raw['title'] ?? '').trim(),
      objective: String(raw['objective'] ?? '').trim(),
      prompt_hint: String(raw['prompt_hint'] ?? raw['promptHint'] ?? '').trim(),
      min_turns_to_complete: this.asNullableNumber(
        raw['min_turns_to_complete'] ?? raw['minTurnsToComplete'],
      ),
      min_avg_overall: this.asNullableNumber(raw['min_avg_overall'] ?? raw['minAvgOverall']),
      max_scored_turns: this.asNullableNumber(raw['max_scored_turns'] ?? raw['maxScoredTurns']),
    };
  }

  private asNullableString(value: unknown): string | null {
    if (value == null) return null;
    const s = String(value).trim();
    return s ? s : null;
  }

  private asNullableNumber(value: unknown): number | null {
    if (value == null) return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
}
