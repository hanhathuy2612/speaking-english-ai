import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import type { ReviewAttempt, ReviewCard, ReviewState } from "../../api/types";
import { AppBar } from "../../components/AppBar";
import { Lead } from "../../components/Lead";
import { CheckIcon, MicIcon, SpeakerIcon, XIcon } from "../../components/Icons";
import { Chip, type Status, StatusLine } from "../../components/ui";
import { WordDiff } from "../../components/WordDiff";
import { ReplayButton } from "../../components/ReplayButton";
import { useMic } from "../../hooks/useMic";
import { useRecordings } from "../../hooks/useRecordings";
import type { WithAudio } from "../../lib/replay";
import { fmtDue, localDay } from "../../lib/review";
import "../../styles/review.css";

type Tally = { good: number; again: number; nextDue: string[] };

function Stats({ s }: { s: ReviewState["stats"] }) {
  return (
    <div className="review-stats">
      <Chip tone={s.due ? "warning" : "success"}>
        {s.due ? `${s.due} thẻ đến hạn hôm nay` : "Không còn thẻ đến hạn"}
      </Chip>
      <Chip>{s.active} thẻ đang ôn</Chip>
      <Chip tone={s.learned ? "success" : ""}>{s.learned} thẻ đã thuộc</Chip>
      {s.recall != null && (
        <Chip title="Tỉ lệ bạn chấm 'Nhớ được' trong 30 ngày qua">
          Nhớ được {s.recall}% ({s.reviews} lần ôn)
        </Chip>
      )}
    </div>
  );
}

/** The front of a card: what to say. The NOTE stays hidden until revealed. */
function Front({ c }: { c: ReviewCard }) {
  return (
    <>
      <p className="eyebrow">
        {c.unit_title} · {c.kind === "note" ? "Sửa câu đã nói" : "Mẫu câu chưa dùng"}
      </p>
      <p className="review-question" lang="en">
        {c.question}
      </p>
      {c.kind === "note" ? (
        <div className="review-said">
          <span className="review-label">Lần trước bạn nói</span>
          <p lang="en">{c.said}</p>
          <span className="review-ask">Nói lại câu này cho đúng và tự nhiên hơn, theo trí nhớ.</span>
        </div>
      ) : (
        <div className="review-said">
          <span className="review-label">Trả lời câu hỏi, có dùng mẫu câu</span>
          <p lang="en" className="review-phrase">
            {c.target}
          </p>
        </div>
      )}
    </>
  );
}

/** The back: what was heard, the NOTE (word by word when spoken), and the suggested grade. */
function Back({ c, a }: { c: ReviewCard; a: WithAudio<ReviewAttempt> | null }) {
  return (
    <div className="review-back" aria-live="polite">
      {a && (
        <div className="review-heard">
          <ReplayButton src={a.audio} />
          <span>Máy nghe được: {a.heard || "(không nghe thấy gì)"}</span>
        </div>
      )}
      {c.kind === "note" ? (
        <div className="review-answer">
          <span className="review-label">Cách nói tốt hơn (NOTE)</span>
          {a?.items ? <WordDiff items={a.items} /> : <p lang="en">{c.target}</p>}
          {a?.items && (
            <p className="review-hint">
              Từ gạch chân là chỗ bạn nói khác NOTE. Nói khác chưa chắc là sai: nếu đúng ý và đúng ngữ pháp thì cứ chấm
              &quot;Nhớ được&quot;.
            </p>
          )}
        </div>
      ) : (
        a && (
          <p className={`review-check ${a.phrase_used ? "pass" : "fail"}`}>
            <span className="criterion-mark" aria-hidden>
              {a.phrase_used ? <CheckIcon size={12} /> : <XIcon size={12} />}
            </span>
            {a.phrase_used ? "Có dùng mẫu câu" : "Máy chưa nghe thấy mẫu câu"}
          </p>
        )
      )}
    </div>
  );
}

export function ReviewPage() {
  const [params] = useSearchParams();
  const session = params.get("session");
  const [data, setData] = useState<ReviewState | null>(null);
  const [queue, setQueue] = useState<ReviewCard[]>([]);
  const [pos, setPos] = useState(0);
  const [attempt, setAttempt] = useState<WithAudio<ReviewAttempt> | null>(null);
  const keepRecording = useRecordings();
  const [revealed, setRevealed] = useState(false);
  const [status, setStatus] = useState<Status>({ text: "", state: "" });
  const [busy, setBusy] = useState(false);
  const [tally, setTally] = useState<Tally>({ good: 0, again: 0, nextDue: [] });
  const requeued = useRef(new Set<number>());
  const audio = useRef<HTMLAudioElement | null>(null);

  const load = useCallback(async () => {
    const res: ReviewState = await (
      await fetch(`/api/review${session ? `?session=${encodeURIComponent(session)}` : ""}`)
    ).json();
    setData(res);
    setQueue(res.cards);
    setPos(0);
    setAttempt(null);
    setRevealed(false);
    setTally({ good: 0, again: 0, nextDue: [] });
    requeued.current.clear();
  }, [session]);

  useEffect(() => {
    document.title = "Ôn tập";
    void load();
    return () => audio.current?.pause();
  }, [load]);

  const card = queue[pos];
  const finished = data !== null && pos >= queue.length;

  const submit = async (blob: Blob) => {
    if (!card) return;
    setBusy(true);
    setStatus({ text: "Đang nhận dạng…", state: "busy" });
    try {
      const res = await fetch(`/api/review/${card.id}/attempt`, { method: "POST", body: blob });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setAttempt({ ...(await res.json()), audio: keepRecording(blob) });
      setRevealed(true);
      setStatus({ text: "", state: "" });
    } catch (e) {
      setStatus({ text: `Không nhận dạng được: ${e instanceof Error ? e.message : e}`, state: "error" });
    } finally {
      setBusy(false);
    }
  };

  const mic = useMic({
    onStart: () => audio.current?.pause(),
    onRecording: () => setStatus({ text: "Đang ghi âm… bấm lần nữa khi nói xong", state: "recording" }),
    onRecorded: (blob) => void submit(blob),
    onTooShort: () => setStatus({ text: "Ghi âm quá ngắn, hãy nói hết rồi mới bấm dừng.", state: "warn" }),
    onError: (msg) => setStatus({ text: `Không mở được micro: ${msg}`, state: "error" }),
  });

  const next = () => {
    setPos((p) => p + 1);
    setAttempt(null);
    setRevealed(false);
    setStatus({ text: "", state: "" });
  };

  const grade = async (result: "good" | "again") => {
    if (!card) return;
    setBusy(true);
    try {
      const body = {
        result,
        heard: attempt?.heard ?? null,
        correct: attempt?.correct ?? null,
        total: attempt?.total ?? null,
      };
      const res = await fetch(`/api/review/${card.id}/grade`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const { due }: { due: string } = await res.json();
      setTally((t) => ({ ...t, [result]: t[result] + 1, nextDue: [...t.nextDue, due] }));
      // A forgotten card comes back once more at the end of this round.
      if (result === "again" && !requeued.current.has(card.id)) {
        requeued.current.add(card.id);
        setQueue((q) => [...q, card]);
      }
      next();
    } catch (e) {
      setStatus({ text: `Không lưu được: ${e instanceof Error ? e.message : e}`, state: "error" });
    } finally {
      setBusy(false);
    }
  };

  const suspend = async () => {
    if (!card || !confirm("Bỏ thẻ này? Thẻ sẽ không xuất hiện trong các lần ôn sau.")) return;
    await fetch(`/api/review/${card.id}/suspend`, { method: "POST" });
    setQueue((q) => q.filter((c, i) => i <= pos || c.id !== card.id));
    next();
  };

  const listen = () => {
    if (!card) return;
    audio.current?.pause();
    audio.current = new Audio(`/api/review/${card.id}/audio`);
    void audio.current.play().catch(() => setStatus({ text: "Không phát được câu mẫu.", state: "error" }));
  };

  const today = localDay();

  return (
    <>
      <AppBar />
      <main className="review">
        <div className="review-head">
          <h1>{session ? "Ôn lỗi của buổi này" : "Ôn tập hôm nay"}</h1>
          <Lead className="review-lead" summary="Nói lại theo trí nhớ trước, rồi mới xem đáp án.">
            Mỗi câu bạn được sửa (NOTE) và mỗi mẫu câu bạn bỏ sót thành một thẻ. Hãy nói lại theo trí nhớ trước, rồi mới
            xem đáp án, vì nhớ ra được mới là học thật. Nhớ được thì thẻ quay lại sau 1, 3, 7, 14, 30 ngày; chưa nhớ thì
            ôn lại ngày mai. Bạn tự chấm; app chỉ gợi ý bằng mức trùng từ với NOTE, không dùng AI chấm.
          </Lead>
          {data && <Stats s={data.stats} />}
        </div>

        {data && !data.enabled && (
          <p className="card review-note">Lịch sử đang tắt (HISTORY_DB để trống), nên chưa có thẻ ôn nào.</p>
        )}

        {card && (
          <section className="card review-card" aria-label="Thẻ ôn">
            <div className="review-progress">
              <span>
                Thẻ {pos + 1}/{queue.length}
              </span>
              {card.reviews > 0 && <span>đã ôn {card.reviews} lần</span>}
            </div>
            <Front c={card} />

            {!revealed && (
              <div className="review-mic">
                <button
                  className={`mic${mic.recording ? " rec" : ""}`}
                  {...mic.buttonProps}
                  disabled={busy}
                  aria-label={mic.recording ? "Đang ghi âm, bấm để dừng" : "Bấm để nói"}
                >
                  <MicIcon />
                </button>
                <div className="review-mic-text">
                  <StatusLine
                    status={status.text ? status : { text: "Bấm micro để nói, bấm lần nữa khi xong.", state: "" }}
                  />
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => setRevealed(true)}
                    disabled={busy || mic.recording}
                  >
                    Không nhớ, xem đáp án
                  </button>
                </div>
              </div>
            )}

            {revealed && (
              <>
                <Back c={card} a={attempt} />
                <div className="review-actions">
                  <button className="btn btn-sm" onClick={listen}>
                    <SpeakerIcon /> Nghe
                  </button>
                  <button className="btn btn-sm" onClick={() => (setAttempt(null), setRevealed(false))} disabled={busy}>
                    Nói lại
                  </button>
                </div>
                {/* The suggested grade (from the objective checks) is the highlighted one. */}
                <div className="review-grade">
                  <button
                    className={`btn${attempt?.suggest === "again" || !attempt ? " btn-primary" : ""}`}
                    onClick={() => void grade("again")}
                    disabled={busy}
                  >
                    Chưa nhớ
                  </button>
                  <button
                    className={`btn${attempt?.suggest === "good" ? " btn-primary" : ""}`}
                    onClick={() => void grade("good")}
                    disabled={busy}
                  >
                    Nhớ được
                  </button>
                </div>
                {status.text && <StatusLine status={status} />}
              </>
            )}

            <button className="btn btn-ghost btn-sm review-suspend" onClick={() => void suspend()} disabled={busy}>
              Bỏ thẻ này
            </button>
          </section>
        )}

        {finished && (
          <section className="card review-done" aria-live="polite">
            {queue.length === 0 ? (
              <>
                <h2>{session ? "Buổi này không có câu nào cần ôn" : "Hôm nay không còn thẻ nào đến hạn"}</h2>
                <p>
                  {session
                    ? "Các câu trả lời của buổi này không có NOTE khác với câu bạn nói."
                    : "Thẻ mới sinh ra sau mỗi buổi tập ở phòng tập. Quay lại ngày mai nhé."}
                </p>
              </>
            ) : (
              <>
                <h2>Xong lượt ôn</h2>
                <p>
                  Nhớ được {tally.good} lần, cần ôn lại {tally.again} lần.
                  {tally.nextDue.length > 0 && ` Thẻ gần nhất quay lại ${fmtDue([...tally.nextDue].sort()[0], today)}.`}
                </p>
              </>
            )}
            <div className="review-actions">
              {!session && data && data.stats.due > data.cards.length && (
                <button className="btn btn-primary" onClick={() => void load()}>
                  Ôn tiếp
                </button>
              )}
              {session && (
                <Link className="btn btn-primary" to="/review">
                  Ôn các thẻ đến hạn
                </Link>
              )}
              <Link className="btn" to="/">
                Về phòng tập
              </Link>
            </div>
          </section>
        )}
      </main>
    </>
  );
}
