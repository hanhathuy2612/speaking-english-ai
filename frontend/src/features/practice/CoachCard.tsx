import type { ShadowResult as ShadowData } from "../../api/types";
import { BulbIcon, MicIcon, PlayIcon } from "../../components/Icons";
import { Chip } from "../../components/ui";
import { ReplayButton } from "../../components/ReplayButton";
import { WordDiff } from "../../components/WordDiff";
import type { WithAudio } from "../../lib/replay";

type Result = WithAudio<ShadowData>;

/** Word-by-word result of reading the NOTE aloud (docs/features/shadowing.md). */
function ShadowResult({ r }: { r: Result }) {
  const { correct, total, accuracy } = r.compare;
  const pct = Math.round(accuracy * 100);
  const o = r.original;
  const faster = o?.wpm_speaking != null && r.speech.wpm_speaking != null && r.speech.wpm_speaking > o.wpm_speaking;
  const fewer = !!o && r.speech.long_pauses < o.long_pauses;
  return (
    <div className="shadow-result" aria-live="polite">
      <WordDiff items={r.compare.items} />
      <p className="shadow-heard">Máy nghe được: {r.heard}</p>
      <div className="meta">
        <ReplayButton src={r.audio} />
        <Chip tone={pct >= 90 ? "success" : "warning"}>
          {correct === total ? `Đúng hết ${total}/${total} từ` : `Đúng ${correct}/${total} từ (${pct}%)`}
        </Chip>
        {r.speech.wpm_speaking != null ? (
          <Chip tone={faster ? "success" : ""}>
            Khi nói {r.speech.wpm_speaking} từ/phút
            {o?.wpm_speaking != null ? ` · lần đầu ${o.wpm_speaking}` : ""}
          </Chip>
        ) : (
          <Chip>Câu ngắn, chưa tính tốc độ</Chip>
        )}
        <Chip tone={fewer ? "success" : ""}>
          {r.speech.long_pauses} lần ngắt dài{o ? ` · lần đầu ${o.long_pauses}` : ""}
        </Chip>
      </div>
      <p className="shadow-legend">
        Gạch chân cam: máy nghe thành từ khác (chữ nhỏ bên dưới). Gạch ngang: máy không nghe thấy. Dấu +: bạn
        nói thêm.
      </p>
    </div>
  );
}

export function CoachCard({
  coach,
  shadow,
  onPlay,
  onShadow,
  onCancelShadow,
}: {
  coach: { text: string; retry: boolean };
  shadow: { waiting: boolean; result: Result | null };
  onPlay: () => void;
  onShadow: () => void;
  onCancelShadow: () => void;
}) {
  const cls = ["card", "coach", shadow.waiting && "shadowing", shadow.result && "has-result"].filter(Boolean);
  return (
    <section className={cls.join(" ")}>
      <div className="coach-head">
        <span className="coach-icon" aria-hidden>
          <BulbIcon />
        </span>
        <span className="coach-label">
          {coach.retry ? "Câu mẫu để bạn nói theo" : "Cách nói tự nhiên hơn, thử nói lại"}
        </span>
        {coach.retry && <Chip tone="warning">Chưa đủ ý, hãy trả lời lại</Chip>}
      </div>
      <p className="coach-text">{coach.text}</p>
      {shadow.result && <ShadowResult r={shadow.result} />}
      <div className="coach-actions">
        <button className="btn btn-sm" onClick={onPlay}>
          <PlayIcon />
          Nghe câu này
        </button>
        <button className="btn btn-sm btn-primary" onClick={onShadow} disabled={shadow.waiting}>
          <MicIcon size={14} />
          {shadow.waiting ? "Đang chờ bạn đọc…" : shadow.result ? "Thử lại" : "Nói lại câu này"}
        </button>
        {shadow.waiting && (
          <button className="btn btn-sm btn-ghost" onClick={onCancelShadow}>
            Hủy
          </button>
        )}
      </div>
    </section>
  );
}
