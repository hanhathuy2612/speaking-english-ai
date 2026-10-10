import { type PointerEvent, useEffect, useRef, useState } from "react";
import type { HistorySession } from "../../api/types";
import { fmtDate, fmtNum, niceMax } from "../../lib/format";

type Key = "wpm_speaking" | "pauses_per_100_words";
const M = { top: 12, right: 44, bottom: 26, left: 36 };

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

/**
 * Single-series line chart over sessions: recessive grid with 4 ticks from zero, 2px line with a
 * 10% area wash, 8px points with a surface ring, a direct label on the latest value only, and a
 * crosshair + tooltip that snaps to the nearest session. The sessions table is the non-visual view.
 */
export function LineChart({ sessions, field, unit }: { sessions: HistorySession[]; field: Key; unit: string }) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<{ i: number; x: number; y: number } | null>(null);
  const pts = sessions.filter((s) => s[field] != null);
  const H = 220;

  if (!pts.length)
    return (
      <div className="chart" ref={ref}>
        <div className="chart-empty">Chưa có dữ liệu</div>
      </div>
    );

  const iw = W - M.left - M.right;
  const ih = H - M.top - M.bottom;
  const maxV = niceMax(Math.max(...pts.map((p) => p[field] as number)) * 1.1);
  const x = (i: number) => M.left + (pts.length === 1 ? iw / 2 : (i / (pts.length - 1)) * iw);
  const y = (v: number) => M.top + ih - (v / maxV) * ih;
  const coords = pts.map((p, i) => [x(i), y(p[field] as number)] as const);
  const line = coords.map(([cx, cy], i) => `${i ? "L" : "M"}${cx},${cy}`).join(" ");
  const last = coords[coords.length - 1];

  // Sparse x labels: first, last and a few in between so they never collide.
  const every = Math.max(1, Math.ceil(pts.length / Math.max(1, Math.floor(iw / 70))));
  const xLabels = pts
    .map((p, i) => ({ i, p }))
    .filter(({ i }) => i === pts.length - 1 || (i % every === 0 && pts.length - 1 - i >= every));

  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const r = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    let i = 0;
    coords.forEach(([cx], k) => {
      if (Math.abs(cx - px) < Math.abs(coords[i][0] - px)) i = k;
    });
    setHover({ i, x: e.clientX, y: e.clientY });
  };

  return (
    <div className="chart" ref={ref}>
      {W >= 120 && (
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Biểu đồ ${unit} theo buổi tập`}>
          {[0, 1, 2, 3, 4].map((k) => {
            const v = (maxV / 4) * k;
            return (
              <g key={k}>
                <line className="grid" x1={M.left} x2={M.left + iw} y1={y(v)} y2={y(v)} />
                <text className="tick" x={M.left - 8} y={y(v) + 4} textAnchor="end">
                  {fmtNum(Math.round(v * 10) / 10)}
                </text>
              </g>
            );
          })}
          {xLabels.map(({ i, p }) => (
            <text key={p.id} className="tick" x={x(i)} y={H - 6} textAnchor="middle">
              {fmtDate(p.started_at, false)}
            </text>
          ))}
          {pts.length > 1 && (
            <>
              <path className="area" d={`${line} L${last[0]},${y(0)} L${coords[0][0]},${y(0)} Z`} />
              <path className="line" d={line} />
            </>
          )}
          {hover && <line className="crosshair" x1={coords[hover.i][0]} x2={coords[hover.i][0]} y1={M.top} y2={M.top + ih} />}
          {coords.map(([cx, cy], i) => (
            <circle key={pts[i].id} className={`point${hover?.i === i ? " active" : ""}`} cx={cx} cy={cy} r={4} />
          ))}
          <text className="end-label" x={last[0] + 10} y={last[1] + 4}>
            {fmtNum(pts[pts.length - 1][field])}
          </text>
          <rect
            className="hit"
            x={M.left - 10}
            y={M.top}
            width={iw + 20}
            height={ih}
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
          />
        </svg>
      )}
      {hover && (
        <div
          className="tooltip"
          role="tooltip"
          style={{ left: Math.min(hover.x + 14, window.innerWidth - 250), top: hover.y - 64 }}
        >
          <strong>
            {fmtNum(pts[hover.i][field])} {unit}
          </strong>
          <span>
            {fmtDate(pts[hover.i].started_at)} · {pts[hover.i].unit_title}
          </span>
        </div>
      )}
    </div>
  );
}
