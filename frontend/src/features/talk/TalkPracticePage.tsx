import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { api, postAudio } from "../../api/http";
import type { TalkData, TalkPracticeResult } from "../../api/types";
import { AppBar } from "../../components/AppBar";
import { Recorder } from "../../components/Recorder";
import { ReplayButton } from "../../components/ReplayButton";
import { Chip, type Status } from "../../components/ui";
import { useRecordings } from "../../hooks/useRecordings";
import { fmtClock } from "../../lib/check";
import { fmtDate, fmtNum } from "../../lib/format";
import type { WithAudio } from "../../lib/replay";
import { nextPrompt } from "../../lib/talks";
import { CompareRows, FrameList, StuckList, useTalkRecorder } from "./TalkParts";
import "../../styles/check.css";

const GOAL = 120;

/** Two-minute practice talks after a talk lesson (docs/features/talk-lessons.md): the talk's own
 * prompts, the frame on screen, measured like a check but stored as practice. */
export function TalkPracticePage() {
  const { talkId = "" } = useParams();
  const [talk, setTalk] = useState<TalkData | null>(null);
  const [error, setError] = useState("");
  const [promptId, setPromptId] = useState("");
  const [result, setResult] = useState<WithAudio<TalkPracticeResult> | null>(null);
  const [scoring, setScoring] = useState(false);
  const [status, setStatus] = useState<Status>({ text: "", state: "" });
  const keepRecording = useRecordings();

  const load = useCallback(async () => {
    const t = await api<TalkData>(`/api/talks/${encodeURIComponent(talkId)}`);
    setTalk(t);
    return t;
  }, [talkId]);

  useEffect(() => {
    load()
      .then((t) => {
        document.title = `${t.title_vi} · Luyện nói`;
        setPromptId(
          nextPrompt(
            t.practice,
            t.attempts.map((a) => a.prompt_id),
          ).id,
        );
      })
      .catch((e) => setError(e.message));
  }, [load]);

  const submit = async (blob: Blob) => {
    setScoring(true);
    setStatus({ text: "Đang nhận dạng và đo…", state: "busy" });
    try {
      const url = `/api/talks/${encodeURIComponent(talkId)}/practice/${encodeURIComponent(promptId)}`;
      const res = await postAudio<TalkPracticeResult>(url, blob);
      setResult({ ...res, audio: keepRecording(blob) });
      setStatus({ text: "", state: "" });
      void load();
    } catch (e) {
      setStatus({ text: `Không chấm được: ${e instanceof Error ? e.message : e}`, state: "error" });
    } finally {
      setScoring(false);
    }
  };

  const { mic, elapsed } = useTalkRecorder((blob) => void submit(blob), setStatus);

  if (error)
    return (
      <>
        <AppBar />
        <main className="check">
          <p className="form-error">{error}</p>
        </main>
      </>
    );
  if (!talk) return <AppBar />;

  const prompt = talk.practice.find((p) => p.id === promptId) ?? talk.practice[0];
  const busy = mic.recording || scoring;

  return (
    <>
      <AppBar />
      <main className="check">
        <div className="check-head">
          <p className="eyebrow">Luyện nói 2 phút</p>
          <h1>{talk.title_vi}</h1>
          <p className="check-lead">
            Nói 2 phút theo dàn ý bên dưới. Đây là đề luyện, không phải đề kiểm tra: kết quả chỉ để bạn so với lần
            trước, không tính vào bài kiểm tra hay lộ trình. <Link to={`/talk/${talk.id}`}>Học lại bài giảng</Link>
          </p>
        </div>

        <section className="card check-task">
          <div className="check-task-head">
            <p className="eyebrow">Đề luyện</p>
            <button
              className="btn btn-ghost btn-sm"
              disabled={busy}
              onClick={() => {
                setResult(null);
                setPromptId(
                  nextPrompt(
                    talk.practice,
                    talk.attempts.map((a) => a.prompt_id),
                    promptId,
                  ).id,
                );
              }}
            >
              Đổi đề
            </button>
          </div>
          <p className="check-prompt" lang="en">
            {prompt.text}
          </p>
          <p className="check-hint">{prompt.hint}</p>
          <FrameList steps={result ? result.steps : talk.frame} />
          <Recorder
            recording={mic.recording}
            disabled={scoring}
            elapsed={elapsed}
            goal={GOAL}
            goalLabel={`mục tiêu ${fmtClock(GOAL)}`}
            status={status.text ? status : { text: "Bấm nút micro để bắt đầu, bấm lần nữa khi nói xong.", state: "" }}
            onToggle={() => {
              if (!mic.recording) setResult(null);
              mic.toggle();
            }}
          />
        </section>

        {result && (
          <section className="card check-result" aria-live="polite">
            <div className="check-result-head">
              <h2>Kết quả</h2>
              <Chip tone={result.steps.every((s) => s.done) ? "success" : ""}>
                Đủ {result.steps.filter((s) => s.done).length}/{result.steps.length} bước dàn ý
              </Chip>
            </div>
            {!result.measurable && (
              <p className="check-warn">
                Cần nói ít nhất 30 giây bằng tiếng Anh thì app mới tính tốc độ và ngập ngừng.
              </p>
            )}
            <CompareRows now={result} before={result.previous} beforeLabel="lần trước" />
            <h3 className="talk-h3">Chỗ bạn ngập ngừng giữa câu</h3>
            <StuckList points={result.stuck} />
            <details className="check-text">
              <summary>Máy nghe được ({result.words} từ)</summary>
              <p>{result.text || "(không nghe được gì)"}</p>
            </details>
            <div className="check-actions">
              <ReplayButton src={result.audio} label="Nghe lại bài nói" />
            </div>
          </section>
        )}

        {talk.attempts.length > 0 && (
          <section className="card table-card">
            <h2>Các lần luyện</h2>
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
                      Từ/phút
                    </th>
                    <th scope="col" className="num">
                      Ngập ngừng / 100 từ
                    </th>
                    <th scope="col" className="num">
                      Dàn ý
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {[...talk.attempts].reverse().map((a) => (
                    <tr key={a.id}>
                      <td>{fmtDate(a.created_at)}</td>
                      <td className="check-prompt-cell">{a.prompt}</td>
                      <td className="num">{fmtClock(a.duration_s)}</td>
                      <td className="num">{fmtNum(a.wpm_speaking)}</td>
                      <td className="num">{fmtNum(a.hesitations_per_100)}</td>
                      <td className="num">
                        {a.steps_done}/{a.steps_total}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>
    </>
  );
}
