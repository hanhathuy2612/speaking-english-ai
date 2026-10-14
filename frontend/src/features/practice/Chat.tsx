import { type ReactNode, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import type { SessionSummary, Speech } from "../../api/types";
import { CheckIcon, UndoIcon } from "../../components/Icons";
import { ReplayButton } from "../../components/ReplayButton";
import { Chip, type Tone } from "../../components/ui";
import type { ChatItem } from "./useInterview";

/** One short line ("15 từ · 121 từ/phút"); tap it for every number. */
function SpeechChips({ speech }: { speech: Speech }) {
  const [open, setOpen] = useState(false);
  if (!speech?.words) return null;
  const parts = [`${speech.words} từ`];
  if (speech.wpm_speaking != null) parts.push(`${speech.wpm_speaking} từ/phút`);
  if (speech.long_pauses > 0) parts.push(`${speech.long_pauses} lần ngắt dài`);
  const details: string[] = [];
  if (speech.wpm == null) details.push("Câu ngắn, chưa tính tốc độ");
  else {
    details.push(`Khi nói ${speech.wpm_speaking} từ/phút`);
    // Only differs from the speaking rate when there were pauses.
    if (speech.wpm !== speech.wpm_speaking) details.push(`Tính cả ngắt ${speech.wpm} từ/phút`);
  }
  details.push(`${speech.long_pauses} lần ngắt dài`);
  return (
    <>
      <button
        type="button"
        className={`chip chip-btn${speech.long_pauses > 2 ? " chip-warning" : ""}`}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {parts.join(" · ")}
      </button>
      {speech.low_conf.length > 0 && <Chip tone="warning">Máy nghe chưa chắc: {speech.low_conf.join(", ")}</Chip>}
      {open && details.map((d) => <Chip key={d}>{d}</Chip>)}
    </>
  );
}

function Message({
  item,
  partner,
  onUndo,
}: {
  item: Extract<ChatItem, { kind: "ai" | "me" }>;
  partner: string;
  onUndo?: () => void;
}) {
  const me = item.kind === "me";
  return (
    <div className={`msg ${item.kind}${me && item.unclear ? " unclear" : ""}`}>
      {!me && (
        <div className="avatar" aria-hidden>
          AI
        </div>
      )}
      <div className="msg-body">
        <div className="who">{me ? "Bạn" : partner}</div>
        <div className="bubble">{item.text}</div>
        {me && (
          <div className="meta">
            {item.unclear && (
              <Chip tone="warning">
                {item.unclear === "not_english"
                  ? "Chưa phải tiếng Anh, AI chưa trả lời"
                  : "Máy nghe chưa rõ, AI chưa trả lời"}
              </Chip>
            )}
            <ReplayButton src={item.audio} />
            {onUndo && (
              <button type="button" className="btn btn-ghost btn-sm undo-btn" onClick={onUndo}>
                <UndoIcon />
                Máy nghe sai, nói lại
              </button>
            )}
            <SpeechChips speech={item.speech} />
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryCard({ s }: { s: SessionSummary }) {
  const stats: [string, string][] = [
    [`${s.questions}`, `câu hỏi, trong ${s.turns} lượt`],
    [`${s.phrases_used.length}/${s.phrases_used.length + s.phrases_missed.length}`, "mẫu câu đã dùng"],
  ];
  if (s.wpm != null) stats.push([`${s.wpm_speaking}`, "từ/phút khi nói"]);
  if (s.spoken_turns) stats.push([`${s.long_pauses}`, `lần ngắt dài / ${s.spoken_turns} lượt nói`]);
  const row = (label: string, items: string[], tone: Tone) =>
    items.length > 0 && (
      <div className="summary-row">
        <p className="eyebrow">{label}</p>
        <div className="chips">
          {items.map((t) => (
            <Chip key={t} tone={tone}>
              {t}
            </Chip>
          ))}
        </div>
      </div>
    );
  return (
    <section className="card summary">
      <h2>
        <span style={{ color: "var(--success)", display: "inline-flex" }}>
          <CheckIcon size={18} width={2.5} />
        </span>
        <span>Tổng kết phiên</span>
      </h2>
      <div className="stats">
        {stats.map(([value, label]) => (
          <div className="stat" key={label}>
            <div className="stat-value">{value}</div>
            <div className="stat-label">{label}</div>
          </div>
        ))}
      </div>
      {row("Đã dùng", s.phrases_used, "success")}
      {row("Chưa dùng", s.phrases_missed, "")}
      <div className="summary-actions">
        {s.session_id != null && (
          <Link className="btn btn-sm btn-primary" to={`/review?session=${s.session_id}`}>
            Ôn lỗi của buổi này
          </Link>
        )}
        <Link className="btn btn-sm" to="/history">
          Xem tiến bộ qua các buổi
        </Link>
      </div>
    </section>
  );
}

/**
 * The conversation. `tail` (the coach card) follows the last message and scrolls with it, so it never
 * covers the conversation on a phone; `tailKey` changes when the tail grows, to scroll it into view.
 */
export function Chat({
  items,
  partner,
  onUndo,
  tail,
  tailKey,
}: {
  items: ChatItem[];
  partner: string;
  onUndo?: () => void;
  tail?: ReactNode;
  tailKey?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight });
  }, [items, tailKey]);
  // "Máy nghe sai, nói lại" belongs to the last accepted answer: that is the one undo removes.
  const lastMe = onUndo ? items.findLast((it) => it.kind === "me" && !it.unclear) : undefined;
  return (
    <div className="chat" ref={ref}>
      <div className="chat-log" aria-live="polite">
        {items.map((it) =>
          it.kind === "summary" ? (
            <SummaryCard key={it.id} s={it.summary} />
          ) : (
            <Message key={it.id} item={it} partner={partner} onUndo={it === lastMe ? onUndo : undefined} />
          ),
        )}
      </div>
      {tail}
    </div>
  );
}
