import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import type { DrillBest, DrillResult, DrillSet, DrillState } from "../../api/types";
import { AppBar } from "../../components/AppBar";
import { Lead } from "../../components/Lead";
import { MicIcon, SpeakerIcon } from "../../components/Icons";
import { Chip, type Status, StatusLine } from "../../components/ui";
import { WordDiff } from "../../components/WordDiff";
import { ReplayButton } from "../../components/ReplayButton";
import { useMic } from "../../hooks/useMic";
import { useRecordings } from "../../hooks/useRecordings";
import { bestTone, isNewBest, markFocus, passedCount } from "../../lib/drills";
import type { WithAudio } from "../../lib/replay";
import "../../styles/sounds.css";

const accuracyTone = (acc: number | null) => (acc == null ? "" : acc >= 90 ? "success" : "warning");

function SetCard({ s, active, onPick }: { s: DrillSet; active: boolean; onPick: () => void }) {
  const passed = passedCount(s.sentences, s.best);
  return (
    <li>
      <button className={`card set-card${active ? " active" : ""}`} onClick={onPick} aria-pressed={active}>
        <span className="set-title">{s.title}</span>
        <span className="set-measured">
          {s.id === "mine" ? `${s.sentences.length} câu` : `Đã đo trên giọng bạn: ${s.measured}`}
        </span>
        {s.accuracy == null ? (
          <Chip>Chưa tập</Chip>
        ) : (
          // Two different numbers, both labelled: sentences passed at least once (best reading), and the
          // recent level that the stage gate uses (last attempts, mistakes included).
          <span className="set-stats">
            <Chip tone={passed === s.sentences.length ? "success" : ""}>
              Đạt {passed}/{s.sentences.length} câu
            </Chip>
            <Chip tone={accuracyTone(s.accuracy)} title={`Từ trọng tâm đúng trong ${s.attempts} lần đọc gần nhất của nhóm`}>
              Gần đây đúng {s.accuracy}%
            </Chip>
          </span>
        )}
      </button>
    </li>
  );
}

type Fresh = WithAudio<DrillResult> & { newBest: boolean; first: boolean };

/** "14/10 16:03" from a local ISO time (history stores local time without a zone). */
const fmtDate = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)} ${iso.slice(11, 16)}`;

function Result({ r, head }: { r: WithAudio<DrillResult>; head?: ReactNode }) {
  if (!r.heard) return <p className="drill-empty">Máy không nghe thấy gì. Kiểm tra micro rồi thử lại.</p>;
  const all = r.correct === r.total;
  return (
    <div className="drill-result" aria-live="polite">
      {head && <div className="drill-result-head">{head}</div>}
      <WordDiff items={r.items} />
      <p className="drill-heard">Máy nghe được: {r.heard}</p>
      <div className="drill-meta">
        <ReplayButton src={r.audio} />
        <Chip tone={r.focus_correct === r.focus_total ? "success" : "warning"}>
          Từ trọng tâm: đúng {r.focus_correct}/{r.focus_total}
        </Chip>
        <Chip tone={all ? "success" : ""}>
          Cả câu: đúng {r.correct}/{r.total} từ
        </Chip>
      </div>
    </div>
  );
}

export function SoundsPage() {
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<DrillState | null>(null);
  const [index, setIndex] = useState(0);
  const [result, setResult] = useState<Fresh | null>(null);
  const keepRecording = useRecordings();
  const [status, setStatus] = useState<Status>({ text: "", state: "" });
  const [scoring, setScoring] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);

  const load = useCallback(async () => {
    const fresh: DrillState = await (await fetch("/api/drills")).json();
    // Keep the sentences already on screen: the personal set changes as you read, and the
    // position in it should not jump while you practise. Only the stats are refreshed.
    setData((old) =>
      old
        ? { ...fresh, sets: fresh.sets.map((s) => ({ ...s, sentences: old.sets.find((o) => o.id === s.id)?.sentences ?? s.sentences })) }
        : fresh,
    );
  }, []);

  useEffect(() => {
    document.title = "Luyện phát âm";
    void load();
    return () => audio.current?.pause();
  }, [load]);

  const set = data?.sets.find((s) => s.id === params.get("set")) ?? data?.sets[0];
  const sentence = set?.sentences[Math.min(index, set.sentences.length - 1)];
  const best: DrillBest | undefined = sentence ? set?.best?.[sentence.id] : undefined;

  const pick = (id: string) => {
    setParams({ set: id }, { replace: true });
    setIndex(0);
    setResult(null);
    setStatus({ text: "", state: "" });
  };

  const goTo = (i: number) => {
    setIndex(i);
    setResult(null);
    setStatus({ text: "", state: "" });
  };
  const go = (step: number) => {
    if (set) goTo((Math.min(index, set.sentences.length - 1) + step + set.sentences.length) % set.sentences.length);
  };

  const listen = (slow: boolean) => {
    if (!set || !sentence) return;
    audio.current?.pause();
    audio.current = new Audio(`/api/drills/${set.id}/${sentence.id}/audio${slow ? "?slow=1" : ""}`);
    void audio.current.play().catch(() => setStatus({ text: "Không phát được câu mẫu.", state: "error" }));
  };

  const submit = async (blob: Blob) => {
    if (!set || !sentence) return;
    const previous = best; // before this reading: is the new one better?
    setScoring(true);
    setStatus({ text: "Đang nhận dạng…", state: "busy" });
    try {
      const res = await fetch(`/api/drills/${set.id}/${sentence.id}`, { method: "POST", body: blob });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const r: DrillResult = await res.json();
      setResult({ ...r, audio: keepRecording(blob), newBest: !!r.heard && isNewBest(r, previous), first: !previous });
      setStatus({ text: "", state: "" });
      void load();
    } catch (e) {
      setStatus({ text: `Không chấm được: ${e instanceof Error ? e.message : e}`, state: "error" });
    } finally {
      setScoring(false);
    }
  };

  const mic = useMic({
    onStart: () => {
      audio.current?.pause();
      setResult(null);
      setStatus({ text: "Đang mở micro…", state: "busy" });
    },
    onRecording: () => setStatus({ text: "Đang ghi âm… bấm lần nữa khi đọc xong", state: "recording" }),
    onRecorded: (blob) => void submit(blob),
    onTooShort: () => setStatus({ text: "Ghi âm quá ngắn, hãy đọc hết rồi mới bấm dừng.", state: "warn" }),
    onError: (msg) => setStatus({ text: `Không mở được micro: ${msg}`, state: "error" }),
  });

  return (
    <>
      <AppBar />
      <main className="sounds">
        <div className="sounds-head">
          <h1>Luyện phát âm</h1>
          <Lead className="sounds-lead" summary="Nghe câu mẫu, bấm micro và đọc to. App chấm các từ trọng tâm (in đậm).">
            Mỗi nhóm nhắm vào một lỗi máy đã đo được trên giọng bạn. Nghe câu mẫu, bấm micro (hoặc giữ phím Space) và đọc to.
            App so từng từ với câu mẫu và chấm riêng các <strong>từ trọng tâm</strong> (in đậm). Máy nhận dạng đôi khi tự
            &quot;sửa&quot; từ gần đúng, nên đạt 100% chưa chắc là phát âm chuẩn, nhưng sai thì gần như chắc chắn là chưa rõ.
          </Lead>
          {data && (
            <p className="sounds-recent">
              {data.recent.accuracy == null
                ? "Chưa có lần đọc nào."
                : `${data.recent.attempts} lần đọc gần nhất (mọi nhóm, tính cả lần sai): đúng ${data.recent.accuracy}% từ trọng tâm. Mục tiêu qua giai đoạn: từ 90%.`}
            </p>
          )}
        </div>

        {data && !data.enabled && (
          <p className="card sounds-note">Lịch sử đang tắt (HISTORY_DB để trống), kết quả sẽ không được lưu.</p>
        )}

        {data && (
          <ul className="set-grid" aria-label="Các nhóm âm">
            {data.sets.map((s) => (
              <SetCard key={s.id} s={s} active={s.id === set?.id} onPick={() => pick(s.id)} />
            ))}
          </ul>
        )}

        {set && (
          <section className="card drill" aria-labelledby="drill-title">
            <div className="drill-head">
              <h2 id="drill-title">{set.title}</h2>
              {sentence && (
                <span className="drill-count">
                  Câu {Math.min(index, set.sentences.length - 1) + 1}/{set.sentences.length}
                </span>
              )}
            </div>
            {set.sentences.length > 1 && (
              <ol className="drill-dots" aria-label="Các câu trong nhóm">
                {set.sentences.map((x, i) => {
                  const b = set.best?.[x.id];
                  const tone = bestTone(b);
                  const on = i === Math.min(index, set.sentences.length - 1);
                  return (
                    <li key={x.id}>
                      <button
                        className={`drill-dot${tone ? ` ${tone}` : ""}${on ? " on" : ""}`}
                        onClick={() => goTo(i)}
                        disabled={mic.recording}
                        aria-current={on ? "step" : undefined}
                        aria-label={`Câu ${i + 1}: ${
                          b ? `tốt nhất đúng ${b.focus_correct}/${b.focus_total} từ trọng tâm` : "chưa đọc"
                        }`}
                      >
                        {i + 1}
                      </button>
                    </li>
                  );
                })}
              </ol>
            )}
            <p className="drill-tip">{set.tip}</p>

            {sentence ? (
              <>
                <p className="drill-sentence" lang="en">
                  {markFocus(sentence.text, sentence.focus).map((w, i) => (
                    <span key={i} className={w.focus ? "focus" : undefined}>
                      {w.text}{" "}
                    </span>
                  ))}
                </p>
                <div className="drill-listen">
                  <button className="btn btn-sm" onClick={() => listen(false)} disabled={mic.recording}>
                    <SpeakerIcon /> Nghe mẫu
                  </button>
                  <button className="btn btn-sm btn-ghost" onClick={() => listen(true)} disabled={mic.recording}>
                    Nghe chậm
                  </button>
                </div>

                <div className="drill-mic">
                  <button
                    className={`mic${mic.recording ? " rec" : ""}`}
                    {...mic.buttonProps}
                    disabled={scoring}
                    aria-label={mic.recording ? "Đang ghi âm, bấm để dừng" : "Bấm để đọc"}
                  >
                    <MicIcon />
                  </button>
                  <StatusLine
                    status={status.text ? status : { text: "Bấm micro để đọc, bấm lần nữa khi xong.", state: "" }}
                  />
                </div>

                {result ? (
                  <Result
                    r={result}
                    head={
                      result.newBest ? (
                        <Chip tone="success">{result.first ? "Lần đọc đầu tiên của câu này" : "Kết quả tốt nhất mới"}</Chip>
                      ) : (
                        best && (
                          <span className="drill-best-note">
                            Chưa vượt lần tốt nhất: đúng {best.focus_correct}/{best.focus_total} từ trọng tâm,{" "}
                            {best.correct}/{best.total} từ cả câu
                          </span>
                        )
                      )
                    }
                  />
                ) : (
                  best && (
                    <Result
                      r={{ ...best, audio: best.audio_url ?? undefined }}
                      head={
                        <>
                          <span className="drill-best-label">Lần đọc tốt nhất của bạn</span>
                          <span className="drill-best-note">
                            {fmtDate(best.created_at)} · đã đọc {best.attempts} lần
                          </span>
                        </>
                      }
                    />
                  )
                )}

                <div className="drill-nav">
                  <button className="btn btn-sm" onClick={() => go(-1)} disabled={mic.recording || set.sentences.length < 2}>
                    Câu trước
                  </button>
                  <button
                    className={`btn btn-sm${result ? " btn-primary" : ""}`}
                    onClick={() => go(1)}
                    disabled={mic.recording || set.sentences.length < 2}
                  >
                    Câu tiếp
                  </button>
                </div>
              </>
            ) : (
              <p className="drill-empty">
                Chưa có câu nào. Khi bạn đọc sai một câu ở phòng tập (nói lại câu mẫu) hoặc ở các nhóm trên, câu đó sẽ hiện ở
                đây.
              </p>
            )}
          </section>
        )}
      </main>
    </>
  );
}
