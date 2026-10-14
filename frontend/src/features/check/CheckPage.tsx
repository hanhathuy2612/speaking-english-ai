import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { api, postAudio } from "../../api/http";
import type { CheckReport, CheckRow, CheckState } from "../../api/types";
import { AppBar } from "../../components/AppBar";
import { Lead } from "../../components/Lead";
import { CheckIcon, XIcon } from "../../components/Icons";
import { Recorder } from "../../components/Recorder";
import { Chip, type Status } from "../../components/ui";
import { ReplayButton } from "../../components/ReplayButton";
import { useMic } from "../../hooks/useMic";
import { useRecordings } from "../../hooks/useRecordings";
import { criterionValue, fmtClock } from "../../lib/check";
import type { WithAudio } from "../../lib/replay";
import { fmtDate, fmtNum, latestWithDelta } from "../../lib/format";
import { StuckList } from "../talk/TalkParts";
import { CheckLearn } from "./CheckLearn";
import "../../styles/check.css";

const MAX_SECONDS = 150; // stop automatically a little after the 2-minute target

function Result({ r, onNext }: { r: WithAudio<CheckReport>; onNext: () => void }) {
  const all = r.passed === r.criteria.length;
  return (
    <section className="card check-result" aria-live="polite">
      <div className="check-result-head">
        <h2>Kết quả</h2>
        <Chip tone={all ? "success" : "warning"}>
          Đạt {r.passed}/{r.criteria.length} tiêu chí
        </Chip>
      </div>
      {!r.measurable && (
        <p className="check-warn">
          Cần nói ít nhất 30 giây bằng tiếng Anh thì app mới tính tốc độ và ngập ngừng. Hãy thử lại và nói lâu hơn.
        </p>
      )}
      <ul className="criteria">
        {r.criteria.map((c) => (
          <li key={c.key} className={c.passed ? "pass" : "fail"}>
            <span className="criterion-mark" aria-hidden>
              {c.passed ? <CheckIcon size={12} /> : <XIcon size={12} />}
            </span>
            <span className="criterion-label">
              {c.label}
              <span className="sr-only">{c.passed ? ": đạt" : ": chưa đạt"}</span>
            </span>
            <span className="criterion-value">{criterionValue(c)}</span>
          </li>
        ))}
      </ul>
      <h3 className="talk-h3">Chỗ bạn ngập ngừng giữa câu ({r.stuck.length})</h3>
      <StuckList points={r.stuck} />
      {r.talk && (
        <p className="check-talk-tip">
          Đây là dạng đề <strong>{r.talk.title_vi.toLowerCase()}</strong>. Bài giảng{" "}
          <Link to={`/talk/${r.talk.id}`}>{r.talk.title_vi}</Link> dạy dàn ý 2 phút và các câu nối ý cho dạng đề này.
        </p>
      )}
      <details className="check-text">
        <summary>Máy nghe được ({r.words} từ)</summary>
        <p>{r.text || "(không nghe được gì)"}</p>
      </details>
      <div className="check-actions">
        <ReplayButton src={r.audio} label="Nghe lại bài nói" />
        <button className="btn btn-primary" onClick={onNext}>
          Làm đề khác
        </button>
      </div>
    </section>
  );
}

/** Talk lessons: how to speak for two minutes on each kind of question (docs/features/talk-lessons.md). */
function Talks({ talks }: { talks: CheckState["talks"] }) {
  return (
    <section className="card talk-lessons">
      <h2>Học cách nói 2 phút</h2>
      <p className="check-learn-hint">
        Mỗi dạng đề có một bài giảng: giáo viên dạy dàn ý 5 bước và các câu nối ý, bạn đọc theo, rồi luyện nói 2 phút
        với đề luyện riêng (không bao giờ là đề kiểm tra).
      </p>
      <ul className="talk-cards">
        {talks.map((t) => (
          <li key={t.id} className="talk-card">
            <div>
              <p className="talk-card-title">{t.title_vi}</p>
              <p className="talk-card-goal">{t.goal}</p>
              <p className="talk-card-meta">
                {t.finished ? "Đã học bài giảng" : "Chưa học"}
                {t.practiced > 0 && ` · ${t.practiced} lần luyện`}
              </p>
            </div>
            <div className="talk-card-actions">
              <Link className={`btn btn-sm${t.finished ? "" : " btn-primary"}`} to={`/talk/${t.id}`}>
                {t.finished ? "Học lại" : "Học"}
              </Link>
              {t.finished > 0 && (
                <Link className="btn btn-sm btn-primary" to={`/talk/${t.id}/practice`}>
                  Luyện nói
                </Link>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Past({ checks }: { checks: CheckRow[] }) {
  if (!checks.length) return null;
  const speed = latestWithDelta(
    checks.map((c) => c.wpm_speaking),
    false,
    "lần đầu",
  );
  const pauses = latestWithDelta(
    checks.map((c) => c.hesitations_per_100),
    true,
    "lần đầu",
  );
  return (
    <section className="card table-card check-past">
      <h2>Các lần kiểm tra</h2>
      <p className="check-trend">
        Tốc độ khi nói gần nhất: <strong>{fmtNum(speed.value)} từ/phút</strong> ({speed.delta.text}). Ngập ngừng giữa
        câu / 100 từ: <strong>{fmtNum(pauses.value)}</strong> ({pauses.delta.text}).
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Thời gian</th>
              <th scope="col">Đề</th>
              <th scope="col" className="num">
                Thời lượng
              </th>
              <th scope="col" className="num">
                Từ/phút khi nói
              </th>
              <th scope="col" className="num">
                Ngập ngừng / 100 từ
              </th>
              <th scope="col" className="num">
                Đạt
              </th>
            </tr>
          </thead>
          <tbody>
            {[...checks].reverse().map((c) => (
              <tr key={c.id}>
                <td>{fmtDate(c.created_at)}</td>
                <td className="check-prompt-cell">{c.prompt}</td>
                <td className="num">{fmtClock(c.duration_s)}</td>
                <td className="num">{fmtNum(c.wpm_speaking)}</td>
                <td className="num">{fmtNum(c.hesitations_per_100)}</td>
                <td className="num">
                  <Chip tone={c.passed === c.total ? "success" : ""}>
                    {c.passed}/{c.total}
                  </Chip>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function CheckPage() {
  const [data, setData] = useState<CheckState | null>(null);
  const [result, setResult] = useState<WithAudio<CheckReport> | null>(null);
  const keepRecording = useRecordings();
  const [scoring, setScoring] = useState(false);
  const [status, setStatus] = useState<Status>({ text: "", state: "" });
  const [elapsed, setElapsed] = useState(0);
  const startedAt = useRef(0);

  const load = useCallback(async (exclude?: string) => {
    const q = exclude ? `?exclude=${encodeURIComponent(exclude)}` : "";
    setData(await api<CheckState>(`/api/check${q}`));
  }, []);

  useEffect(() => {
    document.title = "Kiểm tra nói";
    void load();
  }, [load]);

  const submit = async (blob: Blob) => {
    if (!data) return;
    setScoring(true);
    setStatus({ text: "Đang nhận dạng và đo…", state: "busy" });
    try {
      const report = await postAudio<CheckReport>(`/api/check/${encodeURIComponent(data.prompt.id)}`, blob);
      setResult({ ...report, audio: keepRecording(blob) });
      setStatus({ text: "", state: "" });
      // Refresh the list of past checks but keep the current prompt on screen.
      const fresh = await api<CheckState>("/api/check");
      setData((d) => (d ? { ...d, checks: fresh.checks } : fresh));
    } catch (e) {
      setStatus({ text: `Không chấm được: ${e instanceof Error ? e.message : e}`, state: "error" });
    } finally {
      setScoring(false);
    }
  };

  const mic = useMic({
    spaceKey: false,
    onStart: () => setResult(null),
    onRecording: () => {
      startedAt.current = Date.now();
      setElapsed(0);
      setStatus({ text: "Đang ghi âm… bấm lần nữa khi nói xong", state: "recording" });
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
      if (s >= MAX_SECONDS) mic.stop();
    }, 250);
    return () => clearInterval(id);
  }, [mic.recording, mic.stop]);

  const target = data?.targets.seconds ?? 120;
  const busy = mic.recording || scoring;

  return (
    <>
      <AppBar />
      <main className="check">
        <div className="check-head">
          <h1>Kiểm tra nói</h1>
          <Lead className="check-lead" summary="Nói liền 2 phút về một đề chưa chuẩn bị. App chỉ đo bằng số.">
            Nói liền 2 phút về một đề bạn chưa chuẩn bị. App chỉ đo bằng số (thời lượng, tốc độ, số lần ngập ngừng giữa
            câu, có nói toàn tiếng Anh không), không dùng AI chấm. Lần đầu là bài đầu vào; làm lại sau mỗi giai đoạn để
            xem tiến bộ.
          </Lead>
        </div>

        {data && !data.enabled && (
          <p className="card check-note">Lịch sử đang tắt (HISTORY_DB để trống), kết quả sẽ không được lưu.</p>
        )}

        {data && (
          <section className="card check-task">
            <div className="check-task-head">
              <p className="eyebrow">Đề bài</p>
              <button className="btn btn-ghost btn-sm" onClick={() => void load(data.prompt.id)} disabled={busy}>
                Đổi đề
              </button>
            </div>
            <p className="check-prompt" lang="en">
              {data.prompt.text}
            </p>
            <p className="check-hint">{data.prompt.hint}</p>

            <Recorder
              recording={mic.recording}
              disabled={scoring}
              elapsed={elapsed}
              goal={target}
              goalLabel={`mục tiêu ${fmtClock(target)}`}
              status={status.text ? status : { text: "Bấm nút micro để bắt đầu, bấm lần nữa khi nói xong.", state: "" }}
              onToggle={mic.toggle}
            />
          </section>
        )}

        {result && <Result r={result} onNext={() => (setResult(null), void load(data?.prompt.id))} />}
        {result?.id != null && <CheckLearn key={result.id} report={result} />}
        {data && data.talks.length > 0 && <Talks talks={data.talks} />}
        {data && <Past checks={data.checks} />}
      </main>
    </>
  );
}
