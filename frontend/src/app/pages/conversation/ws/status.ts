import type { TopicUnitWsMeta } from '../model/models';
import { topicUnitFromWsPayload } from './helpers';

export interface StatusRouter {
  clearError(): void;
  setErrorMessage(msg: string): void;
  applyTopicLevelAndSessionId(msg: Record<string, unknown>): void;
  setUnitStepMeta(meta: TopicUnitWsMeta | null): void;
  getLiveSessionId(): number;
  fetchUnitStepSummary(sessionId: number): void;
  setTranscribing(v: boolean): void;
}

export function handleWsStatusPayload(msg: Record<string, unknown>, r: StatusRouter): void {
  const message = msg['message'] as string | undefined;
  /** Keep error banner when only the periodic WS heartbeat fires. */
  if (message === 'pong') {
    return;
  }
  r.clearError();
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
  if (message === 'idle_timeout') {
    r.setErrorMessage(
      'Phiên chat ngắt do lâu không có tín hiệu. Hệ thống sẽ tự kết nối lại — nếu vẫn lỗi, hãy tải lại trang.',
    );
    return;
  }
  if (message === 'rework_applied') {
    r.applyTopicLevelAndSessionId(msg);
    const u = topicUnitFromWsPayload(msg['topicUnit']);
    if (u) r.setUnitStepMeta(u);
  }
}
