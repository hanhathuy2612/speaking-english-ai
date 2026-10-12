import type { AnswerStep, RetellResult as RetellData, ShadowResult as ShadowData } from "../../api/types";
import { BulbIcon, CheckIcon, MicIcon, PlayIcon } from "../../components/Icons";
import { Chip } from "../../components/ui";
import { ReplayButton } from "../../components/ReplayButton";
import { WordDiff } from "../../components/WordDiff";
import type { WithAudio } from "../../lib/replay";

type Result = WithAudio<ShadowData>;
type Retell = WithAudio<RetellData>;

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

/** What to add for a longer answer: hint, English starter, and whether it was already said. */
function Steps({ steps }: { steps: AnswerStep[] }) {
  return (
    <ol className="step-list">
      {steps.map((st) => (
        <li key={st.say} className={st.done ? "done" : undefined}>
          <span className="step-mark" aria-hidden>
            {st.done && <CheckIcon size={10} />}
          </span>
          <span className="step-hint">{st.hint}</span>
          <span className="step-say">{st.say}</span>
          {st.done && <span className="sr-only">(đã có)</span>}
        </li>
      ))}
    </ol>
  );
}

/** The longer answer next to the first one (docs/features/answer-steps.md). */
function RetellResult({ r }: { r: Retell }) {
  const done = r.steps.filter((st) => st.done).length;
  const o = r.original;
  const longer = r.speech.words > r.original_words;
  const fewer = !!o && r.speech.long_pauses < o.long_pauses;
  return (
    <div className="retell-result" aria-live="polite">
      <p className="retell-heard">{r.heard}</p>
      <div className="meta">
        <ReplayButton src={r.audio} />
        <Chip tone={longer ? "success" : "warning"}>
          {r.speech.words} từ · lần đầu {r.original_words}
        </Chip>
        <Chip tone={done === r.steps.length ? "success" : done ? "" : "warning"}>
          Đủ {done}/{r.steps.length} ý
        </Chip>
        {r.speech.wpm_speaking != null && (
          <Chip>
            Khi nói {r.speech.wpm_speaking} từ/phút{o?.wpm_speaking != null ? ` · lần đầu ${o.wpm_speaking}` : ""}
          </Chip>
        )}
        <Chip tone={fewer ? "success" : ""}>
          {r.speech.long_pauses} lần ngắt dài{o ? ` · lần đầu ${o.long_pauses}` : ""}
        </Chip>
      </div>
    </div>
  );
}

export function CoachCard({
  coach,
  shadow,
  onPlay,
  onShadow,
  onCancelShadow,
  retell,
  onRetell,
  onCancelRetell,
}: {
  coach: { text: string; retry: boolean; steps: AnswerStep[] };
  shadow: { waiting: boolean; result: Result | null };
  onPlay: () => void;
  onShadow: () => void;
  onCancelShadow: () => void;
  retell: { waiting: boolean; result: Retell | null };
  onRetell: () => void;
  onCancelRetell: () => void;
}) {
  const cls = [
    "card",
    "coach",
    shadow.waiting && "shadowing",
    retell.waiting && "retelling",
    shadow.result && "has-result",
  ].filter(Boolean);
  const steps = retell.result?.steps ?? coach.steps;
  return (
    <section className={cls.join(" ")}>
      <div className="coach-head">
        <span className="coach-icon" aria-hidden>
          <BulbIcon />
        </span>
        <span className="coach-label">
          {coach.retry ? "Câu mẫu để bạn nói theo" : "Cách nói tự nhiên hơn"}
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
        {/* With steps below, "Trả lời lại dài hơn" is the main action. */}
        <button className={`btn btn-sm${steps.length ? "" : " btn-primary"}`} onClick={onShadow} disabled={shadow.waiting}>
          <MicIcon size={14} />
          {shadow.waiting ? "Đang chờ bạn đọc…" : shadow.result ? "Thử lại" : "Nói lại câu này"}
        </button>
        {shadow.waiting && (
          <button className="btn btn-sm btn-ghost" onClick={onCancelShadow}>
            Hủy
          </button>
        )}
      </div>
      {steps.length > 0 && (
        <div className="steps">
          <p className="steps-head">Nói dài hơn: trả lời lại và thêm các ý này</p>
          <Steps steps={steps} />
          {retell.result && <RetellResult r={retell.result} />}
          <div className="coach-actions">
            <button className="btn btn-sm btn-primary" onClick={onRetell} disabled={retell.waiting}>
              <MicIcon size={14} />
              {retell.waiting ? "Đang chờ bạn trả lời…" : retell.result ? "Thử lại" : "Trả lời lại dài hơn"}
            </button>
            {retell.waiting && (
              <button className="btn btn-sm btn-ghost" onClick={onCancelRetell}>
                Hủy
              </button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
