import { fmtClock } from "../lib/check";
import { MicIcon, StopIcon } from "./Icons";
import { type Status, StatusLine } from "./ui";

type Props = {
  recording: boolean;
  disabled: boolean;
  elapsed: number; // seconds since recording started
  goal: number; // seconds: the bar fills up to this
  goalLabel: string; // e.g. "mục tiêu 2:00", "tối đa 4:00"
  status: Status;
  onToggle: () => void;
};

/** Tap-to-start / tap-to-stop recorder for long answers (speaking check, 4/3/2 rounds). */
export function Recorder({ recording, disabled, elapsed, goal, goalLabel, status, onToggle }: Props) {
  const pct = Math.min(100, (elapsed / goal) * 100);
  return (
    <div className="recorder">
      <button
        className={`rec-btn${recording ? " on" : ""}`}
        onClick={onToggle}
        disabled={disabled}
        aria-label={recording ? "Dừng và chấm" : "Bắt đầu nói"}
      >
        {recording ? <StopIcon /> : <MicIcon />}
      </button>
      <div className="recorder-main">
        <div className="recorder-time">
          <span className="clock">{fmtClock(elapsed)}</span>
          <span className="goal">{goalLabel}</span>
        </div>
        <div className={`recorder-bar${elapsed >= goal ? " reached" : ""}`} aria-hidden>
          <span style={{ width: `${pct}%` }} />
        </div>
        <StatusLine status={status} />
      </div>
    </div>
  );
}
