const pad = (n: number) => String(n).padStart(2, "0");

/** "11/10 21:15" (or "11/10" without time), in local time. */
export function fmtDate(iso: string, withTime = true): string {
  const d = new Date(iso);
  const date = `${pad(d.getDate())}/${pad(d.getMonth() + 1)}`;
  return withTime ? `${date} ${pad(d.getHours())}:${pad(d.getMinutes())}` : date;
}

/** Vietnamese decimal comma; en dash for missing values. */
export const fmtNum = (v: number | null | undefined): string => (v == null ? "–" : String(v).replace(".", ","));

/** Smallest "nice" axis maximum (1, 2, 2.5, 5 × 10^k) that is >= v. */
export function niceMax(v: number): number {
  if (v <= 0) return 1;
  const step = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * step >= v) return m * step;
  return 10 * step;
}

export type Delta = { text: string; tone?: "good" | "bad" };

/** Latest value of a metric and its change vs the first entry that has it. */
export function latestWithDelta(
  values: (number | null)[],
  lowerIsBetter: boolean,
): { value: number | null; delta: Delta } {
  const vals = values.filter((v): v is number => v != null);
  if (!vals.length) return { value: null, delta: { text: "Chưa có lượt nói đủ dài để tính" } };
  const last = vals[vals.length - 1];
  if (vals.length < 2) return { value: last, delta: { text: "Cần ít nhất 2 buổi để so sánh" } };
  const diff = Math.round((last - vals[0]) * 10) / 10;
  const better = lowerIsBetter ? diff < 0 : diff > 0;
  const sign = diff > 0 ? "+" : diff < 0 ? "−" : "±";
  return {
    value: last,
    delta: {
      text: `${sign}${fmtNum(Math.abs(diff))} so với buổi đầu`,
      tone: diff === 0 ? undefined : better ? "good" : "bad",
    },
  };
}
