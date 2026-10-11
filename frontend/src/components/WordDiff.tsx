import type { CompareItem } from "../api/types";

/**
 * A reference sentence word by word against what was heard (backend utils/compare.py):
 * misheard words are underlined with what the machine heard below, missed words struck through,
 * extra words shown as "+ ...". `focus` words (pronunciation drills) are emphasized.
 */
export function WordDiff({ items }: { items: (CompareItem & { focus?: boolean })[] }) {
  return (
    <p className="word-diff" lang="en">
      {items.map((it, i) =>
        it.kind === "extra" ? (
          <span key={i} className="tok extra" title="Bạn nói thêm">
            + {it.text}
          </span>
        ) : (
          <span
            key={i}
            className={`tok ${it.status}${it.focus ? " focus" : ""}`}
            title={
              it.status === "wrong"
                ? `Máy nghe thành: ${it.heard}`
                : it.status === "miss"
                  ? "Máy không nghe thấy từ này"
                  : undefined
            }
          >
            <span className="tok-text">{it.text}</span>
            {it.status === "wrong" && <span className="tok-heard">{it.heard}</span>}
          </span>
        ),
      )}
    </p>
  );
}
