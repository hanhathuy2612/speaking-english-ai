import type { TopicUnitWsMeta } from '../model/models';
import { topicUnitFromWsPayload } from './helpers';
import {
  WS_STATUS_IDLE_TIMEOUT,
  WS_STATUS_NORMALIZING,
  WS_STATUS_PONG,
  WS_STATUS_REWORK_APPLIED,
  WS_STATUS_ROADMAP_UNIT_COMPLETED,
  WS_STATUS_SESSION_STARTED,
  WS_STATUS_TRANSCRIBING,
} from './protocol';

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
  if (message === WS_STATUS_PONG) {
    return;
  }
  r.clearError();
  if (message === WS_STATUS_SESSION_STARTED) {
    r.applyTopicLevelAndSessionId(msg);
    r.setUnitStepMeta(topicUnitFromWsPayload(msg['topicUnit']));
    return;
  }
  if (message === WS_STATUS_ROADMAP_UNIT_COMPLETED) {
    const sid =
      (msg['sessionId'] as number | undefined) ??
      (r.getLiveSessionId() > 0 ? r.getLiveSessionId() : undefined);
    if (sid != null && sid > 0) r.fetchUnitStepSummary(sid);
    return;
  }
  if (message === WS_STATUS_TRANSCRIBING || message === WS_STATUS_NORMALIZING) {
    r.setTranscribing(true);
    return;
  }
  if (message === WS_STATUS_IDLE_TIMEOUT) {
    r.setErrorMessage(
      'Phiên chat ngắt do lâu không có tín hiệu. Hệ thống sẽ tự kết nối lại — nếu vẫn lỗi, hãy tải lại trang.',
    );
    return;
  }
  if (message === WS_STATUS_REWORK_APPLIED) {
    r.applyTopicLevelAndSessionId(msg);
    const u = topicUnitFromWsPayload(msg['topicUnit']);
    if (u) r.setUnitStepMeta(u);
  }
}
