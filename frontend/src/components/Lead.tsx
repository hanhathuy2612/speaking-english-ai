import type { ReactNode } from "react";
import { ChevronIcon } from "./Icons";

/**
 * A page's introduction: one line always shown, the full explanation behind "Chi tiết",
 * so the content starts near the top on a phone.
 */
export function Lead({ summary, children, className }: { summary: ReactNode; children: ReactNode; className: string }) {
  return (
    <details className={`lead ${className}`}>
      <summary>
        <span>{summary}</span>
        <span className="lead-more">
          Chi tiết
          <ChevronIcon size={14} />
        </span>
      </summary>
      <p className="lead-body">{children}</p>
    </details>
  );
}
