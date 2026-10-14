import { type ReactNode, useEffect, useRef } from "react";
import { XIcon } from "./Icons";

/**
 * Bottom sheet on a native <dialog>: the browser handles the backdrop, focus and Escape.
 * Tapping the backdrop closes it too.
 */
export function Sheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      className="sheet"
      aria-label={title}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()} // the dialog itself is only hit outside the panel
    >
      <div className="sheet-panel">
        <div className="sheet-head">
          <p className="sheet-title">{title}</p>
          <button className="icon-btn sm" onClick={onClose} aria-label="Đóng">
            <XIcon size={14} width={2.5} />
          </button>
        </div>
        <div className="sheet-body">{children}</div>
      </div>
    </dialog>
  );
}
