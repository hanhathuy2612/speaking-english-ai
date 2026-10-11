/** When a card comes back, in learner terms: "ngày mai", "sau 7 ngày". `today` is YYYY-MM-DD. */
export function fmtDue(due: string, today: string): string {
  const days = Math.round((Date.parse(due) - Date.parse(today)) / 86_400_000);
  if (days <= 0) return "hôm nay";
  if (days === 1) return "ngày mai";
  return `sau ${days} ngày`;
}

/** Local date as YYYY-MM-DD (the server schedules in local days too). */
export function localDay(d = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
