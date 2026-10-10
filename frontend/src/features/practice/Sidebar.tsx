import type { Metrics, UnitInfo } from "../../api/types";
import { CheckIcon, ChevronIcon } from "../../components/Icons";
import { Chip } from "../../components/ui";

const TIMING: [keyof Metrics, string][] = [
  ["stt_ms", "Nhận dạng giọng nói"],
  ["llm_first_ms", "Chữ đầu tiên của AI"],
  ["first_audio_ms", "Âm thanh đầu tiên"],
  ["total_ms", "Cả lượt"],
];

const seconds = (ms?: number) => (ms ? `${(ms / 1000).toFixed(1)} giây` : "-");

export function Sidebar({
  unit,
  used,
  metrics,
  conf,
}: {
  unit: UnitInfo | null;
  used: number[];
  metrics: Metrics;
  conf: number | null;
}) {
  const phrases = unit?.phrases ?? [];
  const allUsed = phrases.length > 0 && used.length === phrases.length;
  return (
    <aside className="sidebar">
      <section className="card panel">
        <p className="eyebrow">Mục tiêu</p>
        <p className="goal">{unit?.goal}</p>
      </section>

      <section className="card panel">
        <div className="panel-head">
          <p className="eyebrow">Mẫu câu cần dùng</p>
          <Chip tone={allUsed ? "success" : ""}>
            {used.length}/{phrases.length}
          </Chip>
        </div>
        <ul className="phrases">
          {phrases.map((p, i) => (
            <li key={p.say} className={used.includes(i) ? "used" : undefined}>
              <span className="mark" aria-hidden>
                <CheckIcon />
              </span>
              <span>{p.say}</span>
            </li>
          ))}
        </ul>
      </section>

      <details className="card panel tech">
        <summary>
          <span className="eyebrow">Chỉ số kỹ thuật</span>
          <ChevronIcon />
        </summary>
        <dl className="timing">
          {TIMING.map(([k, label]) => (
            <div key={k} style={{ display: "contents" }}>
              <dt>{label}</dt>
              <dd>{seconds(metrics[k])}</dd>
            </div>
          ))}
          <dt>Độ tin cậy nhận dạng</dt>
          <dd>{conf == null ? "-" : conf.toFixed(2)}</dd>
        </dl>
      </details>
    </aside>
  );
}
