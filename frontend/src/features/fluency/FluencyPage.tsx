import { useCallback, useEffect, useRef, useState } from "react";
import type { FluencyResult, FluencyRound, FluencyRun, FluencyState } from "../../api/types";
import { AppBar } from "../../components/AppBar";
import { Lead } from "../../components/Lead";
import { Recorder } from "../../components/Recorder";
import type { Status } from "../../components/ui";
import { ReplayButton } from "../../components/ReplayButton";
import { useMic } from "../../hooks/useMic";
import { useRecordings } from "../../hooks/useRecordings";
import { fmtClock } from "../../lib/check";
import { roundDelta } from "../../lib/fluency";
import { fmtDate, fmtNum } from "../../lib/format";
import type { WithAudio } from "../../lib/replay";
import "../../styles/fluency.css";

const ROUND_TIPS = [
  "Kể trọn câu chuyện, có mở đầu, các ý chính và kết. Không cần vội.",
  "Kể lại đúng nội dung vừa rồi, giữ đủ các ý, nhưng gọn và nhanh hơn.",
  "Lần cuối: vẫn đủ ý, nói liền một mạch. Những câu đã nói hai lần giờ sẽ ra nhanh hơn.",
];

function RoundsTable({ rounds, limits }: { rounds: WithAudio<FluencyRound>[]; limits: number[] }) {
  const speed = roundDelta(rounds, "wpm_speaking");
  const pauses = roundDelta(rounds, "hesitations_per_100");
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Lần</th>
            <th scope="col" className="num">
              Thời lượng
            </th>
            <th scope="col" className="num">
              Từ/phút khi nói
            </th>
            <th scope="col" className="num">
              Ngập ngừng / 100 từ
            </th>
          </tr>
        </thead>
        <tbody>
          {rounds.map((r) => (
            <tr key={r.round}>
              <td>
                <span className="round-cell">
                  {r.round} <span className="muted">(tối đa {fmtClock(limits[r.round - 1])})</span>
                  <ReplayButton src={r.audio} label="Nghe" />
                </span>
              </td>
              <td className="num">{fmtClock(r.duration_s)}</td>
              <td className="num">{fmtNum(r.wpm_speaking)}</td>
              <td className="num">{fmtNum(r.hesitations_per_100)}</td>
            </tr>
          ))}
        </tbody>
        {(speed || pauses) && (
          <tfoot>
            <tr>
              <th scope="row" colSpan={2}>
                Thay đổi
              </th>
              <td className={`num ${speed?.tone ?? ""}`}>{speed?.text ?? "–"}</td>
              <td className={`num ${pauses?.tone ?? ""}`}>{pauses?.text ?? "–"}</td>
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}

function Past({ runs }: { runs: FluencyRun[] }) {
  const done = runs.filter((r) => r.complete);
  if (!done.length) return null;
  const arrow = (vals: (number | null)[]) => vals.map(fmtNum).join(" → ");
  return (
    <section className="card table-card">
      <h2>Các bài đã làm trọn</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Thời gian</th>
              <th scope="col">Đề</th>
              <th scope="col" className="num">
                Từ/phút khi nói (lần 1 → 3)
              </th>
              <th scope="col" className="num">
                Ngập ngừng / 100 từ
              </th>
            </tr>
          </thead>
          <tbody>
            {[...done].reverse().map((r) => (
              <tr key={r.run}>
                <td>{fmtDate(r.created_at)}</td>
                <td className="fluency-prompt-cell">{r.prompt}</td>
                <td className="num">{arrow(r.rounds.map((x) => x.wpm_speaking))}</td>
                <td className="num">{arrow(r.rounds.map((x) => x.hesitations_per_100))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function FluencyPage() {
  const [data, setData] = useState<FluencyState | null>(null);
  const [run, setRun] = useState<string | null>(null);
  const [results, setResults] = useState<WithAudio<FluencyResult>[]>([]);
  const keepRecording = useRecordings();
  const [scoring, setScoring] = useState(false);
  const [status, setStatus] = useState<Status>({ text: "", state: "" });
  const [elapsed, setElapsed] = useState(0);
  const startedAt = useRef(0);

  const load = useCallback(async (exclude?: string) => {
    const q = exclude ? `?exclude=${encodeURIComponent(exclude)}` : "";
    setData(await (await fetch(`/api/fluency${q}`)).json());
  }, []);

  useEffect(() => {
    document.title = "Nói dài 4–3–2";
    void load();
  }, [load]);

  const limits = data?.rounds ?? [240, 180, 120];
  const finished = results.length >= limits.length;
  const round = Math.min(results.length + 1, limits.length);
  const limit = limits[round - 1];

  const reset = (exclude?: string) => {
    setRun(null);
    setResults([]);
    setElapsed(0);
    setStatus({ text: "", state: "" });
    void load(exclude);
  };

  const submit = async (blob: Blob) => {
    if (!data) return;
    setScoring(true);
    setStatus({ text: "Đang nhận dạng và đo…", state: "busy" });
    try {
      const q = run ? `?run=${run}` : "";
      const res = await fetch(`/api/fluency/${encodeURIComponent(data.prompt.id)}/${round}${q}`, { method: "POST", body: blob });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const r: FluencyResult = await res.json();
      setRun(r.run);
      setResults((rs) => [...rs, { ...r, audio: keepRecording(blob) }]);
      setStatus(
        r.measurable
          ? { text: "", state: "" }
          : { text: "Lần này chưa đủ 30 giây tiếng Anh nên chưa tính tốc độ. Bạn có thể thử lại lần này.", state: "warn" },
      );
      if (results.length + 1 >= limits.length) {
        const fresh: FluencyState = await (await fetch("/api/fluency")).json();
        setData((d) => (d ? { ...d, runs: fresh.runs } : fresh));
      }
    } catch (e) {
      setStatus({ text: `Không chấm được: ${e instanceof Error ? e.message : e}`, state: "error" });
    } finally {
      setScoring(false);
    }
  };

  const mic = useMic({
    spaceKey: false,
    onRecording: () => {
      startedAt.current = Date.now();
      setElapsed(0);
      setStatus({ text: "Đang ghi âm… bấm lần nữa khi kể xong", state: "recording" });
    },
    onRecorded: (blob) => void submit(blob),
    onTooShort: () => setStatus({ text: "Ghi âm quá ngắn, hãy thử lại.", state: "warn" }),
    onError: (msg) => setStatus({ text: `Không mở được micro: ${msg}`, state: "error" }),
  });

  useEffect(() => {
    if (!mic.recording) return;
    const id = setInterval(() => {
      const s = (Date.now() - startedAt.current) / 1000;
      setElapsed(s);
      if (s >= limit) mic.stop(); // the time limit is the point of the exercise
    }, 250);
    return () => clearInterval(id);
  }, [mic.recording, mic.stop, limit]);

  const busy = mic.recording || scoring;

  return (
    <>
      <AppBar />
      <main className="fluency">
        <div className="fluency-head">
          <h1>Nói dài 4–3–2</h1>
          <Lead className="fluency-lead" summary="Kể một chuyện ba lần: 4 phút, 3 phút, rồi 2 phút.">
            Kể cùng một chuyện ba lần, thời gian giảm dần: 4 phút, 3 phút, rồi 2 phút. Lần sau bạn đã có sẵn ý và từ, nên
            sẽ nói nhanh hơn và ít ngập ngừng hơn. App đo từng lần bằng số, không dùng AI chấm. Đề ở đây khác đề của bài kiểm
            tra, để bài kiểm tra luôn là đề bạn chưa luyện.
          </Lead>
        </div>

        {data && !data.enabled && (
          <p className="card fluency-note">Lịch sử đang tắt (HISTORY_DB để trống), kết quả sẽ không được lưu.</p>
        )}

        {data && (
          <section className="card fluency-task">
            <div className="fluency-task-head">
              <p className="eyebrow">Đề bài</p>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => reset(data.prompt.id)}
                disabled={busy || results.length > 0}
                title={results.length ? "Làm hết 3 lần với đề này trước" : undefined}
              >
                Đổi đề
              </button>
            </div>
            <p className="fluency-prompt" lang="en">
              {data.prompt.text}
            </p>
            <p className="fluency-hint">{data.prompt.hint}</p>

            <ol className="round-steps" aria-label="Ba lần kể">
              {limits.map((l, i) => (
                <li
                  key={l}
                  className={i < results.length ? "done" : i === results.length && !finished ? "now" : ""}
                  aria-current={i === results.length && !finished ? "step" : undefined}
                >
                  Lần {i + 1} · {fmtClock(l)}
                </li>
              ))}
            </ol>

            {finished ? (
              <div className="fluency-done">
                <p>
                  Xong cả ba lần. So lần 3 với lần 1: tốc độ nên tăng, ngập ngừng nên giảm. Làm thêm vài đề nữa, rồi làm bài
                  kiểm tra nói để xem phản xạ có chuyển sang đề mới không.
                </p>
                <button className="btn btn-primary" onClick={() => reset(data.prompt.id)}>
                  Làm đề khác
                </button>
              </div>
            ) : (
              <>
                <p className="round-tip">
                  <strong>Lần {round}:</strong> {ROUND_TIPS[round - 1]}
                </p>
                <Recorder
                  recording={mic.recording}
                  disabled={scoring}
                  elapsed={elapsed}
                  goal={limit}
                  goalLabel={`tối đa ${fmtClock(limit)}, tự dừng khi hết giờ`}
                  status={status.text ? status : { text: "Bấm nút micro để bắt đầu kể, bấm lần nữa khi xong.", state: "" }}
                  onToggle={mic.toggle}
                />
              </>
            )}

            {results.length > 0 && (
              <div className="fluency-results">
                <RoundsTable rounds={results} limits={limits} />
                {!busy && (
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => {
                      setResults((rs) => rs.slice(0, -1));
                      setStatus({ text: "", state: "" });
                    }}
                  >
                    Làm lại lần {results.length}
                  </button>
                )}
              </div>
            )}
          </section>
        )}

        {data && <Past runs={data.runs} />}
      </main>
    </>
  );
}
