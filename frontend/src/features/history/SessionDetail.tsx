import { useEffect, useRef, useState } from "react";
import type { HistorySession, HistoryTurn } from "../../api/types";
import { ReplayButton } from "../../components/ReplayButton";
import { Chip } from "../../components/ui";
import { fmtDate } from "../../lib/format";

/** The answers of one past session, each with its recording and NOTE (docs/features/session-history.md). */
export function SessionDetail({ session, onClose }: { session: HistorySession; onClose: () => void }) {
  const [turns, setTurns] = useState<HistoryTurn[] | null>(null);
  const box = useRef<HTMLElement>(null);

  useEffect(() => {
    let live = true;
    setTurns(null);
    void (async () => {
      const data: HistoryTurn[] = await (await fetch(`/api/history/sessions/${session.id}/turns`)).json();
      if (live) setTurns(data);
    })();
    return () => {
      live = false;
    };
  }, [session.id]);

  // Bring the detail into view once its content is there (it sits below a long page).
  useEffect(() => {
    if (turns) box.current?.scrollIntoView({ block: "start" });
  }, [turns]);

  const recorded = turns?.filter((t) => t.audio_url).length ?? 0;
  const spoken = turns?.filter((t) => t.source === "voice").length ?? 0;

  return (
    <section className="card session-detail" ref={box} aria-labelledby="session-detail-title" tabIndex={-1}>
      <div className="session-detail-head">
        <div>
          <p className="eyebrow">Chi tiết buổi tập</p>
          <h2 id="session-detail-title">
            {session.unit_title} · {fmtDate(session.started_at)}
          </h2>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Đóng
        </button>
      </div>
      {turns && spoken > recorded && (
        <p className="session-detail-note">
          {recorded ? `Còn ${spoken - recorded} lượt nói` : "Các lượt nói của buổi này"} không còn file ghi âm (chỉ lưu khi
          SAVE_AUDIO_DIR được đặt trong .env).
        </p>
      )}
      {turns === null && <p className="session-detail-note">Đang tải…</p>}
      <ol className="turn-list">
        {turns?.map((t) => (
          <li key={t.id} className={t.unclear ? "unclear" : undefined}>
            <p className="turn-question" lang="en">
              {t.question}
            </p>
            <div className="turn-answer">
              <p lang="en">{t.answer}</p>
              <div className="turn-meta">
                <ReplayButton src={t.audio_url ?? undefined} />
                {t.source === "text" && <Chip>Gõ chữ</Chip>}
                {t.unclear ? <Chip tone="warning">AI chưa trả lời (nghe chưa rõ hoặc chưa phải tiếng Anh)</Chip> : null}
                {t.wpm_speaking != null && <Chip>{t.wpm_speaking} từ/phút</Chip>}
              </div>
            </div>
            {t.note && (
              <p className="turn-note">
                <span className="turn-note-label">Cách nói tốt hơn (NOTE)</span>
                <span lang="en">{t.note}</span>
              </p>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
