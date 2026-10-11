import { useEffect, useState } from "react";
import { Link } from "react-router";
import type { Topic, UnitStatus } from "../../api/types";
import { AppBar } from "../../components/AppBar";
import { CheckIcon } from "../../components/Icons";
import { Chip } from "../../components/ui";
import { fmtDate } from "../../lib/format";
import { allUnits, pickUnit, unitState } from "../../lib/roadmap";
import "../../styles/roadmap.css";

const STATE_CHIP = {
  done: { tone: "success", text: "Hoàn thành" },
  started: { tone: "warning", text: "Đang tập dở" },
  new: { tone: "", text: "Chưa tập" },
} as const;

function UnitCard({ u, next }: { u: UnitStatus; next: boolean }) {
  const st = unitState(u);
  const chip = STATE_CHIP[st];
  return (
    <li className={`card unit-card ${st}${next ? " next" : ""}`}>
      <div className="unit-head">
        <h3>{u.title}</h3>
        {next ? <Chip tone="warning">Bài tiếp theo</Chip> : <Chip tone={chip.tone}>{chip.text}</Chip>}
      </div>
      <p className="unit-goal">{u.goal}</p>
      <div className="unit-foot">
        <span className="unit-meta">
          {u.questions} câu hỏi
          {u.sessions > 0 && ` · đã tập ${u.sessions} lần · gần nhất ${fmtDate(u.last_at!, false)}`}
        </span>
        <Link className={`btn btn-sm${next ? " btn-primary" : ""}`} to={`/?unit=${encodeURIComponent(u.id)}`}>
          {st === "new" ? "Bắt đầu" : "Luyện lại"}
        </Link>
      </div>
    </li>
  );
}

function TopicSection({ t, index, nextId }: { t: Topic; index: number; nextId: string | null }) {
  const done = t.units.filter((u) => u.completed).length;
  const all = done === t.units.length;
  return (
    <section className="topic" aria-labelledby={`topic-${t.id}`}>
      <div className="topic-head">
        <span className={`topic-step${all ? " done" : ""}`} aria-hidden>
          {all ? <CheckIcon size={14} /> : index + 1}
        </span>
        <div className="topic-text">
          <h2 id={`topic-${t.id}`}>{t.title}</h2>
          <p>{t.description}</p>
        </div>
        <Chip tone={all ? "success" : ""}>
          {done}/{t.units.length} bài
        </Chip>
      </div>
      <ul className="unit-grid">
        {t.units.map((u) => (
          <UnitCard key={u.id} u={u} next={u.id === nextId} />
        ))}
      </ul>
    </section>
  );
}

export function RoadmapPage() {
  const [topics, setTopics] = useState<Topic[] | null>(null);

  useEffect(() => {
    document.title = "Lộ trình luyện phỏng vấn";
    void (async () => setTopics((await (await fetch("/api/units")).json()).topics))();
  }, []);

  const units = allUnits(topics ?? []);
  const done = units.filter((u) => u.completed).length;
  // Only highlight a "next" unit while something is left to finish.
  const nextId = done < units.length ? pickUnit(topics ?? [], null) : null;

  return (
    <>
      <AppBar />
      <main className="roadmap">
        <div className="roadmap-head">
          <h1>Lộ trình luyện phỏng vấn</h1>
          <p className="roadmap-lead">
            Đi lần lượt từ giới thiệu bản thân đến cuối buổi phỏng vấn. Một bài được tính là hoàn thành khi bạn trả
            lời hết các câu hỏi chính.
          </p>
          {topics && (
            <div className="roadmap-progress">
              <div className="roadmap-bar" aria-hidden>
                <span style={{ width: `${units.length ? (done / units.length) * 100 : 0}%` }} />
              </div>
              <span>
                Hoàn thành {done}/{units.length} bài
              </span>
            </div>
          )}
        </div>
        {topics?.map((t, i) => <TopicSection key={t.id} t={t} index={i} nextId={nextId} />)}
      </main>
    </>
  );
}
