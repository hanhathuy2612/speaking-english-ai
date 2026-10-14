import { useState } from "react";
import { api, postAudio } from "../../api/http";
import type { CheckReport, CheckReviewData, RetryResult } from "../../api/types";
import { Recorder } from "../../components/Recorder";
import { ReplayButton } from "../../components/ReplayButton";
import type { Status } from "../../components/ui";
import { useRecordings } from "../../hooks/useRecordings";
import { fmtClock } from "../../lib/check";
import type { WithAudio } from "../../lib/replay";
import { CompareRows, StuckList, useTalkRecorder } from "../talk/TalkParts";

/**
 * Learning from a check after it was scored (docs/features/talk-lessons.md): an AI review of your own
 * talk, review cards for the phrases you lacked, and the same question again. The check's numbers
 * never change, and the question is not given in later checks once you studied it.
 */
export function CheckLearn({ report }: { report: CheckReport }) {
  const [review, setReview] = useState<CheckReviewData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const ask = async () => {
    setLoading(true);
    setError("");
    try {
      setReview(await api<CheckReviewData>(`/api/check/${report.id}/review`, { body: {} }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  if (!review)
    return (
      <section className="card check-learn">
        <h2>Học từ bài nói này</h2>
        <p className="check-learn-hint">
          AI viết lại bài nói của bạn cho tự nhiên (giữ nguyên ý của bạn), gợi ý cách nói tiếp ở từng chỗ bí, và chọn ra
          các cụm từ nên học. Kết quả kiểm tra ở trên không đổi. Sau khi ôn, đề này sẽ không ra lại trong bài kiểm tra,
          để lần kiểm tra sau vẫn là đề bạn chưa chuẩn bị.
        </p>
        {error && <p className="form-error">{error}</p>}
        <div>
          <button className="btn btn-primary" disabled={loading} onClick={() => void ask()}>
            {loading ? "AI đang soạn… (khoảng nửa phút)" : "Học từ bài nói này"}
          </button>
        </div>
      </section>
    );

  return (
    <>
      <section className="card check-learn" aria-live="polite">
        <h2>Cách nói tự nhiên hơn</h2>
        <p className="check-better" lang="en">
          {review.better}
        </p>
        {review.added_facts.length > 0 && (
          <p className="check-warn">
            AI có thêm chi tiết bạn không nói ({review.added_facts.join(", ")}). Khi nói lại, hãy dùng chi tiết thật của
            bạn.
          </p>
        )}
        {review.stuck.length > 0 && (
          <>
            <h3 className="talk-h3">Chỗ bạn bí, và cách nói tiếp</h3>
            <StuckList points={review.stuck} />
          </>
        )}
        <Phrases checkId={report.id!} phrases={review.phrases} />
      </section>
      <Retry report={report} />
    </>
  );
}

function Phrases({ checkId, phrases }: { checkId: number; phrases: CheckReviewData["phrases"] }) {
  const [picked, setPicked] = useState<string[]>(phrases.map((p) => p.say));
  const [done, setDone] = useState("");
  const add = async () => {
    try {
      const r = await api<{ added: number }>(`/api/check/${checkId}/cards`, { body: { phrases: picked } });
      setDone(
        r.added ? `Đã thêm ${r.added} thẻ. Ôn ở trang Ôn tập, theo lịch 1, 3, 7… ngày.` : "Các cụm này đã có thẻ rồi.",
      );
    } catch (e) {
      setDone(e instanceof Error ? e.message : String(e));
    }
  };
  return (
    <>
      <h3 className="talk-h3">Cụm từ nên học</h3>
      <ul className="check-phrases">
        {phrases.map((p) => (
          <li key={p.say}>
            <label className="check-row">
              <input
                type="checkbox"
                checked={picked.includes(p.say)}
                onChange={(e) => setPicked(e.target.checked ? [...picked, p.say] : picked.filter((x) => x !== p.say))}
              />
              <span lang="en" className="check-phrase-say">
                {p.say}
              </span>
              <span className="check-phrase-vi">{p.vi}</span>
            </label>
          </li>
        ))}
      </ul>
      {done ? (
        <p className="form-ok">{done}</p>
      ) : (
        <div>
          <button className="btn" disabled={!picked.length} onClick={() => void add()}>
            Thêm {picked.length} cụm vào thẻ ôn
          </button>
        </div>
      )}
    </>
  );
}

function Retry({ report }: { report: CheckReport }) {
  const [result, setResult] = useState<WithAudio<RetryResult> | null>(null);
  const [scoring, setScoring] = useState(false);
  const [status, setStatus] = useState<Status>({ text: "", state: "" });
  const keepRecording = useRecordings();

  const submit = async (blob: Blob) => {
    setScoring(true);
    setStatus({ text: "Đang nhận dạng và đo…", state: "busy" });
    try {
      const r = await postAudio<RetryResult>(`/api/check/${report.id}/retry`, blob);
      setResult({ ...r, audio: keepRecording(blob) });
      setStatus({ text: "", state: "" });
    } catch (e) {
      setStatus({ text: `Không chấm được: ${e instanceof Error ? e.message : e}`, state: "error" });
    } finally {
      setScoring(false);
    }
  };
  const { mic, elapsed } = useTalkRecorder((blob) => void submit(blob), setStatus);

  return (
    <section className="card check-learn">
      <h2>Nói lại đề này</h2>
      <p className="check-learn-hint">
        Nói lại cả đề, dùng các cụm vừa học. Lần này chỉ là luyện tập: không tính vào bài kiểm tra.
      </p>
      <p className="check-prompt" lang="en">
        {report.prompt.text}
      </p>
      <Recorder
        recording={mic.recording}
        disabled={scoring}
        elapsed={elapsed}
        goal={120}
        goalLabel={`mục tiêu ${fmtClock(120)}`}
        status={status.text ? status : { text: "Bấm nút micro để bắt đầu, bấm lần nữa khi nói xong.", state: "" }}
        onToggle={() => {
          if (!mic.recording) setResult(null);
          mic.toggle();
        }}
      />
      {result && (
        <div aria-live="polite" className="check-retry">
          <CompareRows now={result} before={result.first} beforeLabel="lần kiểm tra" />
          <h3 className="talk-h3">Chỗ còn ngập ngừng</h3>
          <StuckList points={result.stuck} />
          <ReplayButton src={result.audio} label="Nghe lại lần nói này" />
        </div>
      )}
    </section>
  );
}
