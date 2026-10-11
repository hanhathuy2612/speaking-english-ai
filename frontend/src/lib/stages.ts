import type { CheckLevel, Requirement } from "../api/types";
import { fmtClock } from "./check";
import { fmtNum } from "./format";

/** "nói liền 1:30, từ 95 từ/phút, dưới 5 lần ngập ngừng / 100 từ". */
export function checkLevelText(l: CheckLevel): string {
  const parts = [`nói liền ${fmtClock(l.seconds)}`];
  if (l.wpm_speaking != null) parts.push(`từ ${l.wpm_speaking} từ/phút`);
  if (l.hesitations_per_100 != null) parts.push(`dưới ${fmtNum(l.hesitations_per_100)} lần ngập ngừng / 100 từ`);
  return parts.join(", ");
}

/** One stage requirement in learner terms: what is asked and where you are. */
export function requirementText(r: Requirement): { label: string; value: string } {
  switch (r.kind) {
    case "units":
      return { label: "Hoàn thành mọi bài của giai đoạn", value: `${r.done}/${r.total} bài` };
    case "drill_sets":
      return { label: "Tập đủ các nhóm âm", value: `${r.done}/${r.total} nhóm` };
    case "drill_accuracy": {
      const acc = r.accuracy == null ? "chưa tập" : `${r.accuracy}%`;
      return {
        label: `Đọc đúng từ ${r.target}% từ trọng tâm trong ${r.window} câu gần nhất`,
        value: r.attempts < r.window ? `${acc} · mới ${r.attempts}/${r.window} câu` : acc,
      };
    }
    case "fluency_runs":
      return { label: `Làm trọn ${r.total} bài nói dài 4–3–2`, value: `${r.done}/${r.total} bài` };
    case "check": {
      const l = r.latest;
      let value = "chưa làm";
      if (l) {
        const parts = [fmtClock(l.duration_s), `${fmtNum(l.wpm_speaking)} từ/phút`];
        if (r.target.hesitations_per_100 != null) parts.push(`${fmtNum(l.hesitations_per_100)} ngập ngừng`);
        value = `${r.met ? "đạt" : "gần nhất"}: ${parts.join(" · ")}`;
      }
      return { label: `Bài kiểm tra: ${checkLevelText(r.target)}`, value };
    }
  }
}
