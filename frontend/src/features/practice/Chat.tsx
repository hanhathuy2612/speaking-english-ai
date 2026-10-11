import { useEffect, useRef } from "react";
import { Link } from "react-router";
import type { SessionSummary, Speech } from "../../api/types";
import { CheckIcon } from "../../components/Icons";
import { Chip, type Tone } from "../../components/ui";
import type { ChatItem } from "./useInterview";

function SpeechChips({ speech }: { speech: Speech }) {
  if (!speech?.words) return null;
  const chips: [string, Tone][] = [[`${speech.words} từ`, ""]];
  if (speech.wpm == null) chips.push(["Câu ngắn, chưa tính tốc độ", ""]);
  else {
    chips.push([`Khi nói ${speech.wpm_speaking} từ/phút`, ""]);
    chips.push([`Tính cả ngắt ${speech.wpm} từ/phút`, ""]);
  }
  chips.push([`${speech.long_pauses} lần ngắt dài`, speech.long_pauses > 2 ? "warning" : ""]);
  if (speech.low_conf.length) chips.push([`Máy nghe chưa chắc: ${speech.low_conf.join(", ")}`, "warning"]);
  return (
    <>
      {chips.map(([text, tone]) => (
        <Chip key={text} tone={tone}>
          {text}
        </Chip>
      ))}
    </>
  );
}

function Message({ item }: { item: Extract<ChatItem, { kind: "ai" | "me" }> }) {
  const me = item.kind === "me";
  return (
    <div className={`msg ${item.kind}${me && item.unclear ? " unclear" : ""}`}>
      <div className="avatar" aria-hidden>
        {me ? "Bạn" : "AI"}
      </div>
      <div className="msg-body">
        <div className="who">{me ? "Bạn" : "Người phỏng vấn"}</div>
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
      <Link className="btn btn-sm summary-link" to="/history">
        Xem tiến bộ qua các buổi
      </Link>
    </section>
  );
}

export function Chat({ items }: { items: ChatItem[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight });
  }, [items]);
  return (
    <div className="chat" aria-live="polite" ref={ref}>
      {items.map((it) =>
        it.kind === "summary" ? <SummaryCard key={it.id} s={it.summary} /> : <Message key={it.id} item={it} />,
      )}
    </div>
  );
}
