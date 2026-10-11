import { useEffect, useState } from "react";
import { Link } from "react-router";
import type { CheckRow, Topic, UnitStatus } from "../../api/types";
import { AppBar } from "../../components/AppBar";
import { CheckIcon } from "../../components/Icons";
import { Chip } from "../../components/ui";
import { fmtClock } from "../../lib/check";
import { fmtDate, fmtNum } from "../../lib/format";
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

/** Speaking check status: the placement test first, then the latest result. */
function CheckCard({ checks }: { checks: CheckRow[] }) {
  const last = checks[checks.length - 1];
  return (
    <section className="card check-card" aria-label="Bài kiểm tra nói">
      <div className="check-card-text">
        <p className="eyebrow">Bài kiểm tra nói</p>
        {last ? (
          <>
            <h2>
              Lần gần nhất đạt {last.passed}/{last.total} tiêu chí
            </h2>
            <p>
              {fmtDate(last.created_at, false)} · nói {fmtClock(last.duration_s)} · {fmtNum(last.wpm_speaking)} từ/phút
              khi nói · {fmtNum(last.hesitations_per_100)} lần ngập ngừng / 100 từ. Làm lại sau mỗi chủ đề để xem tiến bộ.
            </p>
          </>
        ) : (
          <>
            <h2>Bắt đầu bằng bài kiểm tra đầu vào</h2>
            <p>Nói 2 phút về một đề chưa chuẩn bị để lấy số đo ban đầu. App chỉ đo, không dùng AI chấm.</p>
          </>
        )}
      </div>
      <Link className={`btn${last ? "" : " btn-primary"}`} to="/check">
        {last ? "Kiểm tra lại" : "Làm bài đầu vào"}
      </Link>
    </section>
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
  const [checks, setChecks] = useState<CheckRow[] | null>(null);

  useEffect(() => {
    document.title = "Lộ trình luyện nói";
    void (async () => setTopics((await (await fetch("/api/units")).json()).topics))();
    void (async () => setChecks((await (await fetch("/api/check")).json()).checks))();
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
          <h1>Lộ trình luyện nói</h1>
          <p className="roadmap-lead">
            Đi lần lượt từ giao tiếp hằng ngày, tiếng Anh ở công ty, rồi tới phỏng vấn. Một bài được tính là hoàn
            thành khi bạn trả lời hết các câu hỏi chính. Làm bài kiểm tra nói sau mỗi chủ đề để đo tiến bộ.
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
        {checks && <CheckCard checks={checks} />}
        {topics?.map((t, i) => <TopicSection key={t.id} t={t} index={i} nextId={nextId} />)}
      </main>
    </>
  );
}
