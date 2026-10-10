import type { ReactNode } from "react";

export type Tone = "" | "success" | "warning";

export function Chip({ tone = "", children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return (
    <span className={tone ? `chip chip-${tone}` : "chip"} title={title}>
      {children}
    </span>
  );
}

export type StatusState = "" | "ready" | "busy" | "recording" | "warn" | "error";
export type Status = { text: string; state: StatusState };

/** One-line status with a colored dot driven by data-state (see .status in base.css). */
export function StatusLine({ status }: { status: Status }) {
  return (
    <div className="status" role="status" data-state={status.state}>
      {status.text}
    </div>
  );
}
