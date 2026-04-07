import type { TopicUnitWsMeta } from '../model/models';
import { topicUnitFromWsPayload } from './helpers';

export interface StatusRouter {
  clearError(): void;
  applyTopicLevelAndSessionId(msg: Record<string, unknown>): void;
  setUnitStepMeta(meta: TopicUnitWsMeta | null): void;
  getLiveSessionId(): number;
  fetchUnitStepSummary(sessionId: number): void;
  setTranscribing(v: boolean): void;
}

export function handleWsStatusPayload(msg: Record<string, unknown>, r: StatusRouter): void {
  r.clearError();
  const message = msg['message'] as string | undefined;
  if (message === 'session_started') {
    r.applyTopicLevelAndSessionId(msg);
    r.setUnitStepMeta(topicUnitFromWsPayload(msg['topicUnit']));
    return;
  }
  if (message === 'roadmap_unit_completed') {
    const sid =
      (msg['sessionId'] as number | undefined) ??
      (r.getLiveSessionId() > 0 ? r.getLiveSessionId() : undefined);
    if (sid != null && sid > 0) r.fetchUnitStepSummary(sid);
    return;
  }
  if (message === 'transcribing' || message === 'normalizing') {
    r.setTranscribing(true);
    return;
  }
  if (message === 'rework_applied') {
    r.applyTopicLevelAndSessionId(msg);
    const u = topicUnitFromWsPayload(msg['topicUnit']);
    if (u) r.setUnitStepMeta(u);
  }
}
