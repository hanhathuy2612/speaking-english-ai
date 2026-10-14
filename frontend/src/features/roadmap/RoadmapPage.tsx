import { useEffect, useState } from "react";
import { Link } from "react-router";
import type { CheckRow, Stage, Topic, UnitStatus } from "../../api/types";
import { AppBar } from "../../components/AppBar";
import { Lead } from "../../components/Lead";
import { CheckIcon, LockIcon, XIcon } from "../../components/Icons";
import { Chip } from "../../components/ui";
import { fmtClock } from "../../lib/check";
import { fmtDate, fmtNum } from "../../lib/format";
import { unitLink, unitState } from "../../lib/roadmap";
import { requirementText } from "../../lib/stages";
import "../../styles/roadmap.css";

const STATE_CHIP = {
  done: { tone: "success", text: "Hoàn thành" },
  started: { tone: "warning", text: "Đang tập dở" },
  new: { tone: "", text: "Chưa tập" },
} as const;

const STAGE_CHIP = {
  passed: { tone: "success", text: "Đã qua" },
  current: { tone: "warning", text: "Đang học" },
  locked: { tone: "", text: "Chưa mở" },
} as const;

const PRACTICE = {
  drills: {
    to: "/sounds",
    title: "Luyện phát âm",
    text: "Năm nhóm câu nhắm vào các lỗi đã đo trên giọng bạn, cộng nhóm câu bạn từng đọc sai.",
    action: "Mở trang Phát âm",
  },
  fluency: {
    to: "/fluency",
    title: "Nói dài 4–3–2",
    text: "Kể cùng một chuyện ba lần trong 4, 3 rồi 2 phút; app đo tốc độ và ngập ngừng từng lần.",
    action: "Mở trang Nói dài",
  },
} as const;

function UnitCard({ u, next, locked }: { u: UnitStatus; next: boolean; locked: boolean }) {
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
          {u.lesson ? `Bài giảng + ${u.questions} câu hỏi` : `${u.questions} câu hỏi`}
          {u.sessions > 0 && ` · đã tập ${u.sessions} lần · gần nhất ${fmtDate(u.last_at!, false)}`}
        </span>
        <Link className={`btn btn-sm${next ? " btn-primary" : locked ? " btn-ghost" : ""}`} to={unitLink(u)}>
          {locked ? "Tập trước" : st === "new" ? "Bắt đầu" : "Luyện lại"}
        </Link>
      </div>
    </li>
  );
}

function TopicBlock({ t, nextId, locked }: { t: Topic; nextId: string | null; locked: boolean }) {
  const done = t.units.filter((u) => u.done).length;
  return (
    <div className="topic">
      <div className="topic-head">
        <div className="topic-text">
          <h3>{t.title}</h3>
          <p>{t.description}</p>
        </div>
        <Chip tone={done === t.units.length ? "success" : ""}>
          {done}/{t.units.length} bài
        </Chip>
      </div>
      <ul className="unit-grid">
        {t.units.map((u) => (
          <UnitCard key={u.id} u={u} next={u.id === nextId} locked={locked} />
        ))}
      </ul>
    </div>
  );
}

function StageSection({ s, index, nextId }: { s: Stage; index: number; nextId: string | null }) {
  const chip = STAGE_CHIP[s.status];
  const locked = s.status === "locked";
  const checkMissing = s.requirements.some((r) => r.kind === "check" && !r.met);
  const practice = s.practice && PRACTICE[s.practice];
  const body = (
    <div className="stage-body">
      {practice && (
        <div className="card practice-card">
          <div>
            <h3>{practice.title}</h3>
            <p>{practice.text}</p>
          </div>
          <Link className={`btn btn-sm${s.status === "current" ? " btn-primary" : ""}`} to={practice.to}>
            {practice.action}
          </Link>
        </div>
      )}
      {s.topics.map((t) => (
        <TopicBlock key={t.id} t={t} nextId={nextId} locked={locked} />
      ))}
    </div>
  );
  return (
    <section className={`stage stage-${s.status}`} aria-labelledby={`stage-${s.id}`}>
      <div className="stage-head">
        <span className={`stage-step stage-step-${s.status}`} aria-hidden>
          {s.status === "passed" ? <CheckIcon size={14} /> : locked ? <LockIcon /> : index + 1}
        </span>
        <div className="stage-text">
          <h2 id={`stage-${s.id}`}>
            Giai đoạn {index + 1}: {s.title}
          </h2>
          <p>{s.goal}</p>
        </div>
        <Chip tone={chip.tone}>{chip.text}</Chip>
      </div>

      {s.requirements.length > 0 && (
        <div className="stage-gate">
          <p className="eyebrow">{locked ? "Để qua giai đoạn này, cần" : "Tiêu chí qua giai đoạn"}</p>
          <ul className="criteria">
            {s.requirements.map((r, i) => {
              const { label, value } = requirementText(r);
              return (
                <li key={i} className={r.met ? "pass" : "fail"}>
                  <span className="criterion-mark" aria-hidden>
                    {r.met ? <CheckIcon size={12} /> : <XIcon size={12} />}
                  </span>
                  <span className="criterion-label">
                    {label}
                    <span className="sr-only">{r.met ? ": đạt" : ": chưa đạt"}</span>
                  </span>
                  <span className="criterion-value">{value}</span>
                </li>
              );
            })}
          </ul>
          {s.status === "current" && checkMissing && (
            <Link className="btn btn-sm stage-check-link" to="/check">
              Làm bài kiểm tra nói
            </Link>
          )}
        </div>
      )}

      {s.status === "current" ? (
        body
      ) : (
        <details className="stage-more">
          <summary>{locked ? "Xem trước nội dung (vẫn tập trước được)" : "Xem lại nội dung"}</summary>
          {body}
        </details>
      )}
    </section>
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
              khi nói · {fmtNum(last.hesitations_per_100)} lần ngập ngừng / 100 từ. Kết quả này quyết định bạn qua giai
              đoạn 2, 3 và 4.
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

export function RoadmapPage() {
  const [stages, setStages] = useState<Stage[] | null>(null);
  const [nextId, setNextId] = useState<string | null>(null);
  const [checks, setChecks] = useState<CheckRow[] | null>(null);

  useEffect(() => {
    document.title = "Lộ trình luyện nói";
    void (async () => {
      const data: { stages: Stage[]; next_unit: string | null } = await (await fetch("/api/stages")).json();
      setStages(data.stages);
      setNextId(data.next_unit);
    })();
    void (async () => setChecks((await (await fetch("/api/check")).json()).checks))();
  }, []);

  const passed = stages?.filter((s) => s.status === "passed").length ?? 0;

  return (
    <>
      <AppBar />
      <main className="roadmap">
        <div className="roadmap-head">
          <h1>Lộ trình luyện nói</h1>
          <Lead className="roadmap-lead" summary="Năm giai đoạn, đi lần lượt. Đạt đủ tiêu chí thì mở giai đoạn sau.">
            Năm giai đoạn, đi lần lượt. Một giai đoạn chỉ mở khi giai đoạn trước đạt đủ tiêu chí, và tiêu chí là số đo:
            bài đã hoàn thành, độ chính xác khi đọc, kết quả bài kiểm tra nói. Mức kiểm tra tăng dần qua từng giai đoạn,
            tới mức đích ở giai đoạn 4. Cần luyện gấp một bài chưa mở (ví dụ sắp phỏng vấn) thì vẫn chọn được ở Phòng
            tập.
          </Lead>
          {stages && (
            <div className="roadmap-progress">
              <div className="roadmap-bar" aria-hidden>
                <span style={{ width: `${(passed / stages.length) * 100}%` }} />
              </div>
              <span>
                Đã qua {passed}/{stages.length} giai đoạn
              </span>
            </div>
          )}
        </div>
        {checks && <CheckCard checks={checks} />}
        {stages?.map((s, i) => (
          <StageSection key={s.id} s={s} index={i} nextId={nextId} />
        ))}
      </main>
    </>
  );
}
