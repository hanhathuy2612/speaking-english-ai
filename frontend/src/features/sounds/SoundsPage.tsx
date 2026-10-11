import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import type { DrillResult, DrillSet, DrillState } from "../../api/types";
import { AppBar } from "../../components/AppBar";
import { MicIcon, SpeakerIcon } from "../../components/Icons";
import { Chip, type Status, StatusLine } from "../../components/ui";
import { WordDiff } from "../../components/WordDiff";
import { useHoldToTalk } from "../../hooks/useHoldToTalk";
import { markFocus } from "../../lib/drills";
import "../../styles/sounds.css";

const accuracyTone = (acc: number | null) => (acc == null ? "" : acc >= 90 ? "success" : "warning");

function SetCard({ s, active, onPick }: { s: DrillSet; active: boolean; onPick: () => void }) {
  return (
    <li>
      <button className={`card set-card${active ? " active" : ""}`} onClick={onPick} aria-pressed={active}>
        <span className="set-title">{s.title}</span>
        <span className="set-measured">
          {s.id === "mine" ? `${s.sentences.length} câu` : `Đã đo trên giọng bạn: ${s.measured}`}
        </span>
        <Chip tone={accuracyTone(s.accuracy)}>
          {s.accuracy == null ? "Chưa tập" : `Đúng ${s.accuracy}% từ trọng tâm`}
        </Chip>
      </button>
    </li>
  );
}

function Result({ r }: { r: DrillResult }) {
  if (!r.heard) return <p className="drill-empty">Máy không nghe thấy gì. Kiểm tra micro rồi thử lại.</p>;
  const all = r.correct === r.total;
  return (
    <div className="drill-result" aria-live="polite">
      <WordDiff items={r.items} />
      <p className="drill-heard">Máy nghe được: {r.heard}</p>
      <div className="drill-meta">
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
  const [result, setResult] = useState<DrillResult | null>(null);
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

  const pick = (id: string) => {
    setParams({ set: id }, { replace: true });
    setIndex(0);
    setResult(null);
    setStatus({ text: "", state: "" });
  };

  const go = (step: number) => {
    if (!set) return;
    setIndex((i) => (i + step + set.sentences.length) % set.sentences.length);
    setResult(null);
    setStatus({ text: "", state: "" });
  };

  const listen = (slow: boolean) => {
    if (!set || !sentence) return;
    audio.current?.pause();
    audio.current = new Audio(`/api/drills/${set.id}/${sentence.id}/audio${slow ? "?slow=1" : ""}`);
    void audio.current.play().catch(() => setStatus({ text: "Không phát được câu mẫu.", state: "error" }));
  };

  const submit = async (blob: Blob) => {
    if (!set || !sentence) return;
    setScoring(true);
    setStatus({ text: "Đang nhận dạng…", state: "busy" });
    try {
      const res = await fetch(`/api/drills/${set.id}/${sentence.id}`, { method: "POST", body: blob });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setResult(await res.json());
      setStatus({ text: "", state: "" });
      void load();
    } catch (e) {
      setStatus({ text: `Không chấm được: ${e instanceof Error ? e.message : e}`, state: "error" });
    } finally {
      setScoring(false);
    }
  };

  const mic = useHoldToTalk({
    onStart: () => {
      audio.current?.pause();
      setResult(null);
      setStatus({ text: "Đang ghi âm… thả ra khi đọc xong", state: "recording" });
    },
    onRecorded: (blob) => void submit(blob),
    onTooShort: () => setStatus({ text: "Ghi âm quá ngắn, giữ nút trong lúc đọc.", state: "warn" }),
    onError: (msg) => setStatus({ text: `Không mở được micro: ${msg}`, state: "error" }),
  });

  return (
    <>
      <AppBar />
      <main className="sounds">
        <div className="sounds-head">
          <h1>Luyện phát âm</h1>
          <p className="sounds-lead">
            Mỗi nhóm nhắm vào một lỗi máy đã đo được trên giọng bạn. Nghe câu mẫu, giữ nút micro (hoặc phím Space) và đọc to.
            App so từng từ với câu mẫu và chấm riêng các <strong>từ trọng tâm</strong> (in đậm). Máy nhận dạng đôi khi tự
            &quot;sửa&quot; từ gần đúng, nên đạt 100% chưa chắc là phát âm chuẩn, nhưng sai thì gần như chắc chắn là chưa rõ.
          </p>
          {data && (
            <p className="sounds-recent">
              {data.recent.accuracy == null
                ? "Chưa có lần đọc nào."
                : `${data.window} câu gần nhất: đúng ${data.recent.accuracy}% từ trọng tâm (${data.recent.attempts} câu). Mục tiêu qua giai đoạn: từ 90%.`}
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
                    aria-label="Giữ để đọc"
                  >
                    <MicIcon />
                  </button>
                  <StatusLine
                    status={status.text ? status : { text: "Giữ nút micro hoặc phím Space trong lúc đọc.", state: "" }}
                  />
                </div>

                {result && <Result r={result} />}

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
