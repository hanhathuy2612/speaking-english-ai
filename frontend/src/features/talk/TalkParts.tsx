import { useEffect, useRef, useState } from "react";
import type { AnswerStep, StuckPoint } from "../../api/types";
import { CheckIcon } from "../../components/Icons";
import type { Status } from "../../components/ui";
import { useMic } from "../../hooks/useMic";
import { compareTalks } from "../../lib/talks";
import "../../styles/talk.css";

/** Pieces shared by the talk practice page and learning after a check (docs/features/talk-lessons.md). */

export const MAX_SECONDS = 150; // stop automatically a little after the 2-minute target

/** Tap-to-start / tap-to-stop recording of a long talk, with the elapsed time and an automatic stop. */
export function useTalkRecorder(onRecorded: (blob: Blob) => void, setStatus: (s: Status) => void) {
  const [elapsed, setElapsed] = useState(0);
  const startedAt = useRef(0);
  const mic = useMic({
    spaceKey: false,
    onRecording: () => {
      startedAt.current = Date.now();
      setElapsed(0);
      setStatus({ text: "Đang ghi âm… bấm lần nữa khi nói xong", state: "recording" });
    },
    onRecorded,
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
  return { mic, elapsed };
}

type Measured = Parameters<typeof compareTalks>[0];

/** Speed, length and hesitation next to an earlier talk ("lần đầu", "lần trước"). */
export function CompareRows({ now, before, beforeLabel }: { now: Measured; before: Measured | null; beforeLabel: string }) {
  return (
    <ul className="talk-compare">
      {compareTalks(now, before).map((r) => (
        <li key={r.label} className={r.better == null ? "" : r.better ? "up" : "down"}>
          <span className="talk-compare-label">{r.label}</span>
          <span className="talk-compare-now">{r.now}</span>
          {r.before != null && (
            <span className="talk-compare-before">
              {beforeLabel} {r.before}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Where you hesitated inside a sentence, with a way to go on when the review has one. */
export function StuckList({ points }: { points: StuckPoint[] }) {
  if (!points.length) return <p className="talk-empty">Không có chỗ nào ngập ngừng giữa câu. Tốt lắm!</p>;
  return (
    <ol className="stuck-list">
      {points.map((p, i) => (
        <li key={i}>
          <p className="stuck-said" lang="en">
            …{p.before} <span className="stuck-pause">⏸ {p.pause_s.toString().replace(".", ",")} giây</span>{" "}
            {p.after}…
          </p>
          {p.say && (
            <p className="stuck-say" lang="en">
              → {p.say}
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}

/** The five-step frame of a talk; after a talk, the steps you said are ticked. */
export function FrameList({ steps }: { steps: (Omit<AnswerStep, "done"> & { done?: boolean })[] }) {
  return (
    <ol className="talk-frame">
      {steps.map((st) => (
        <li key={st.say} className={st.done ? "done" : ""}>
          <span className="talk-frame-mark" aria-hidden>
            {st.done ? <CheckIcon size={10} /> : null}
          </span>
          <span className="talk-frame-hint">
            {st.hint}
            {st.done != null && <span className="sr-only">{st.done ? ": đã nói" : ": chưa nói"}</span>}
          </span>
          <span className="talk-frame-say" lang="en">
            {st.say}
          </span>
        </li>
      ))}
    </ol>
  );
}
