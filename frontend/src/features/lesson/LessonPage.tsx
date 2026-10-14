import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import type { LessonData, LessonLine, LessonReading } from "../../api/types";
import { BackIcon, BookIcon, ChatIcon, CheckIcon, MicIcon, SpeakerIcon, TranslateIcon } from "../../components/Icons";
import { ReplayButton } from "../../components/ReplayButton";
import { Chip, type Status, StatusLine } from "../../components/ui";
import { WordDiff } from "../../components/WordDiff";
import { useMic } from "../../hooks/useMic";
import { useRecordings } from "../../hooks/useRecordings";
import { useTeacherVoice } from "../../hooks/useTeacherVoice";
import { afterReading, sentenceKeys } from "../../lib/lesson";
import type { WithAudio } from "../../lib/replay";
import "../../styles/lesson.css";

type Item =
  | { id: number; kind: "teacher"; key: string; line: LessonLine; sentence?: number; vocab?: boolean }
  | { id: number; kind: "me"; text: string }
  | { id: number; kind: "reading"; reading: WithAudio<LessonReading> };

/** ready: waiting for "Sẵn sàng"; read: waiting for a reading; busy: checking one; finished: lesson done. */
type Wait = "ready" | "read" | "busy" | "finished";

let nextId = 1;

/** Lesson part of a unit (docs/features/lesson.md): overview, then the teacher's lecture. */
export function LessonPage() {
  const { unitId = "" } = useParams();
  const [data, setData] = useState<LessonData | null>(null);
  const [missing, setMissing] = useState(false);
  const [lecture, setLecture] = useState(false);
  const [items, setItems] = useState<Item[]>([]);
  const [wait, setWait] = useState<Wait>("ready");
  const [status, setStatus] = useState<Status>({ text: "", state: "" });
  const sentence = useRef(0); // sentence being taught
  const attempts = useRef(0); // readings of that sentence so far
  const voice = useTeacherVoice(unitId);
  const keepRecording = useRecordings();
  const chat = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let live = true;
    fetch(`/api/lessons/${encodeURIComponent(unitId)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d: LessonData) => {
        if (!live) return;
        setData(d);
        document.title = `${d.title} · Bài học`;
      })
      .catch(() => live && setMissing(true));
    return () => {
      live = false;
    };
  }, [unitId]);

  useEffect(() => {
    chat.current?.scrollTo({ top: chat.current.scrollHeight, behavior: "smooth" });
  }, [items]);

  const teacher = (key: string, extra: Partial<Extract<Item, { kind: "teacher" }>> = {}): Item => ({
    id: nextId++,
    kind: "teacher",
    key,
    line: data!.lines[key],
    ...extra,
  });

  /** Teach sentence `i`, or finish the lesson after the last one. */
  const teach = (i: number) => {
    const d = data!;
    sentence.current = i;
    attempts.current = 0;
    if (i < d.sentences.length) {
      setItems((xs) => [...xs, teacher(`s${i}`, { sentence: i }), teacher("read")]);
      voice.enqueue(sentenceKeys(i));
      setWait("read");
      setStatus({ text: "Bấm micro rồi đọc câu in đậm", state: "ready" });
      return;
    }
    setItems((xs) => [...xs, teacher("outro")]);
    voice.enqueue(["outro"]);
    setWait("finished");
    setStatus({ text: "", state: "" });
    void fetch(`/api/lessons/${encodeURIComponent(d.id)}/finish`, { method: "POST" })
      .then((r) => r.json())
      .then((r: { finished: number }) => setData((x) => (x ? { ...x, finished: r.finished } : x)))
      .catch(() => {});
  };

  const start = () => {
    setLecture(true);
    setItems([teacher("intro")]);
    setWait("ready");
    setStatus({ text: "", state: "" });
    voice.playNow("intro"); // inside the tap: unlocks audio on mobile browsers
  };

  const ready = () => {
    setItems((xs) => [...xs, { id: nextId++, kind: "me", text: "Yes, I'm ready!" }, teacher("vocab", { vocab: true })]);
    voice.stop();
    voice.enqueue(["vocab"]);
    teach(0);
  };

  const onRecorded = async (blob: Blob) => {
    if (wait !== "read" || !data) return;
    const i = sentence.current;
    setWait("busy");
    setStatus({ text: "Đang nghe bạn đọc…", state: "busy" });
    const audio = keepRecording(blob);
    let reading: LessonReading;
    try {
      const r = await fetch(`/api/lessons/${encodeURIComponent(data.id)}/read/${i}`, { method: "POST", body: blob });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      reading = await r.json();
    } catch (e) {
      setWait("read");
      setStatus({ text: `Lỗi: ${e instanceof Error ? e.message : e}`, state: "error" });
      return;
    }
    if (!reading.heard) {
      setWait("read");
      setStatus({ text: "Không nghe rõ, hãy đọc lại gần micro hơn.", state: "warn" });
      return;
    }
    attempts.current += 1;
    const outcome = afterReading(reading.compare.accuracy, attempts.current);
    setItems((xs) => [...xs, { id: nextId++, kind: "reading", reading: { ...reading, audio } }, teacher(outcome)]);
    if (outcome === "retry") {
      voice.enqueue(["retry", `say${i}`]);
      setWait("read");
      setStatus({ text: "Nghe lại rồi bấm micro để đọc lần nữa", state: "ready" });
      return;
    }
    voice.enqueue([outcome]);
    teach(i + 1);
  };

  const mic = useMic({
    onStart: voice.stop,
    onRecorded: (blob) => void onRecorded(blob),
    onTooShort: () => setStatus({ text: "Ghi âm quá ngắn. Bấm micro, đọc hết câu rồi bấm lần nữa.", state: "warn" }),
    onError: (msg) => setStatus({ text: `Không mở được micro: ${msg}`, state: "error" }),
    spaceKey: lecture && wait === "read",
  });

  useEffect(() => {
    if (mic.recording) setStatus({ text: "Đang ghi âm… bấm lần nữa để gửi", state: "recording" });
  }, [mic.recording]);

  if (missing) {
    return (
      <div className="lesson-app">
        <div className="lesson-empty">
          <p>Bài này chưa có bài giảng.</p>
          <Link className="btn btn-primary" to={`/?unit=${encodeURIComponent(unitId)}`}>
            Vào phần luyện tập
          </Link>
          <Link className="btn btn-ghost" to="/roadmap">
            Về lộ trình
          </Link>
        </div>
      </div>
    );
  }
  if (!data) return <div className="lesson-app" aria-busy />;

  const practice = `/?unit=${encodeURIComponent(data.id)}`;
  const step = Math.min(sentence.current + 1, data.sentences.length);

  return (
    <div className="lesson-app">
      <header className="lesson-top">
        {lecture ? (
          <button
            className="icon-btn"
            aria-label="Về trang tổng quan bài"
            onClick={() => {
              voice.stop();
              setLecture(false);
            }}
          >
            <BackIcon />
          </button>
        ) : (
          <Link className="icon-btn" to="/roadmap" aria-label="Về lộ trình">
            <BackIcon />
          </Link>
        )}
        <div className="lesson-top-text">
          <p className="lesson-top-title">{data.title}</p>
          <ol className="lesson-steps" aria-label="Các phần của bài">
            <li className={lecture || !data.finished ? "on" : "passed"}>Bài học</li>
            <li className={data.finished && !lecture ? "on" : undefined}>Đóng vai</li>
          </ol>
        </div>
        {lecture && wait !== "finished" && wait !== "ready" && (
          <Chip>
            Câu {step}/{data.sentences.length}
          </Chip>
        )}
      </header>

      {lecture ? (
        <>
          <div className="lesson-chat" ref={chat} aria-live="polite">
            <p className="lesson-section">
              <BookIcon size={16} /> Phần bài giảng
            </p>
            {items.map((it) =>
              it.kind === "teacher" ? (
                <TeacherBubble
                  key={it.id}
                  item={it}
                  data={data}
                  speaking={voice.speaking === it.key}
                  onPlay={voice.playNow}
                />
              ) : it.kind === "me" ? (
                <div key={it.id} className="lesson-msg me">
                  <div className="lesson-bubble">{it.text}</div>
                </div>
              ) : (
                <ReadingBubble key={it.id} r={it.reading} />
              ),
            )}
          </div>

          <div className="lesson-dock">
            <StatusLine status={status} />
            {wait === "ready" && (
              <button className="btn btn-primary btn-lg" onClick={ready}>
                Sẵn sàng
              </button>
            )}
            {(wait === "read" || wait === "busy") && (
              <button
                className={`lesson-mic${mic.recording ? " rec" : ""}`}
                aria-label={mic.recording ? "Đang ghi âm, bấm để gửi" : "Bấm để đọc câu"}
                disabled={wait === "busy"}
                onClick={mic.toggle}
              >
                <MicIcon size={30} />
              </button>
            )}
            {wait === "finished" && (
              <div className="lesson-finish">
                <Link className="btn btn-primary btn-lg" to={practice}>
                  <ChatIcon /> Bắt đầu đóng vai
                </Link>
                <button className="btn btn-ghost" onClick={start}>
                  Học lại bài giảng
                </button>
              </div>
            )}
          </div>
        </>
      ) : (
        <Overview data={data} onStart={start} practice={practice} onPlay={voice.playNow} speaking={voice.speaking} />
      )}
    </div>
  );
}

function TeacherBubble({
  item,
  data,
  speaking,
  onPlay,
}: {
  item: Extract<Item, { kind: "teacher" }>;
  data: LessonData;
  speaking: boolean;
  onPlay: (key: string) => void;
}) {
  const [vi, setVi] = useState(false);
  const s = item.sentence != null ? data.sentences[item.sentence] : null;
  return (
    <div className={`lesson-msg teacher${speaking ? " speaking" : ""}`}>
      <div className="lesson-bubble" lang="en">
        {s ? (
          <>
            {s.use} <strong className="lesson-say">{s.say}</strong>
          </>
        ) : (
          item.line.en
        )}
        {item.vocab && (
          <ul className="lesson-vocab compact">
            {data.vocab.map((w, i) => (
              <li key={w.word}>
                <button className="vocab-btn" onClick={() => onPlay(`w${i}`)} aria-label={`Nghe từ ${w.word}`}>
                  <SpeakerIcon size={14} />
                  <span lang="en">{w.word}</span>
                </button>
                <span className="vocab-vi">{w.vi}</span>
              </li>
            ))}
          </ul>
        )}
        {vi && item.line.vi && (
          <p className="lesson-vi" lang="vi">
            {item.line.vi}
          </p>
        )}
      </div>
      <div className="lesson-tools">
        {item.line.vi && (
          <button
            className={`icon-btn sm${vi ? " on" : ""}`}
            aria-label={vi ? "Ẩn bản dịch" : "Dịch sang tiếng Việt"}
            aria-pressed={vi}
            onClick={() => setVi(!vi)}
          >
            <TranslateIcon />
          </button>
        )}
        <button className="icon-btn sm" aria-label="Nghe lại câu của giáo viên" onClick={() => onPlay(item.key)}>
          <SpeakerIcon />
        </button>
      </div>
    </div>
  );
}

function ReadingBubble({ r }: { r: WithAudio<LessonReading> }) {
  const { correct, total, accuracy } = r.compare;
  const pct = Math.round(accuracy * 100);
  return (
    <div className="lesson-msg me">
      <div className="lesson-bubble reading">
        <WordDiff items={r.compare.items} />
        <div className="meta">
          <Chip tone={pct >= 80 ? "success" : "warning"}>
            {correct === total ? `Đúng hết ${total}/${total} từ` : `Đúng ${correct}/${total} từ`}
          </Chip>
          <ReplayButton src={r.audio} />
        </div>
      </div>
    </div>
  );
}

function Overview({
  data,
  onStart,
  practice,
  onPlay,
  speaking,
}: {
  data: LessonData;
  onStart: () => void;
  practice: string;
  onPlay: (key: string) => void;
  speaking: string | null;
}) {
  const learned = data.finished > 0;
  return (
    <main className="lesson-overview">
      <section className="lesson-hero">
        <h1 lang="en">{data.title}</h1>
        <p className="lesson-goal">{data.goal}</p>
        <div className="chips">
          <Chip>{data.vocab.length} từ vựng</Chip>
          <Chip>{data.sentences.length} câu</Chip>
          {learned && (
            <Chip tone="success">
              <CheckIcon size={10} /> Đã học bài giảng
            </Chip>
          )}
        </div>
      </section>

      <section>
        <h2 className="lesson-h2">Bài tập</h2>
        <div className="lesson-parts">
          <button className={`lesson-part${learned ? "" : " primary"}`} onClick={onStart}>
            <BookIcon />
            <span className="lesson-part-name">Bài học</span>
            <span className="lesson-part-sub">{learned ? "Học lại" : "Bước 1: học từng câu"}</span>
          </button>
          {learned ? (
            <Link className="lesson-part primary" to={practice}>
              <ChatIcon size={22} />
              <span className="lesson-part-name">Đóng vai</span>
              <span className="lesson-part-sub">Bước 2: dùng các câu vừa học</span>
            </Link>
          ) : (
            <div className="lesson-part locked" aria-disabled>
              <ChatIcon size={22} />
              <span className="lesson-part-name">Đóng vai</span>
              <span className="lesson-part-sub">Học xong bài giảng để mở</span>
            </div>
          )}
        </div>
      </section>

      <section>
        <h2 className="lesson-h2">Từ vựng</h2>
        <ul className="lesson-vocab">
          {data.vocab.map((w, i) => (
            <li key={w.word}>
              <button
                className={`icon-btn${speaking === `w${i}` ? " on" : ""}`}
                onClick={() => onPlay(`w${i}`)}
                aria-label={`Nghe từ ${w.word}`}
              >
                <SpeakerIcon />
              </button>
              <span className="vocab-word" lang="en">
                {w.word}
              </span>
              <span className="vocab-vi">{w.vi}</span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="lesson-h2">Câu cần học</h2>
        <ol className="lesson-sentences">
          {data.sentences.map((s, i) => (
            <li key={s.say}>
              <button
                className={`icon-btn${speaking === `say${i}` ? " on" : ""}`}
                onClick={() => onPlay(`say${i}`)}
                aria-label="Nghe câu này"
              >
                <SpeakerIcon />
              </button>
              <div>
                <p className="lesson-sentence" lang="en">
                  {s.say}
                </p>
                <p className="lesson-sentence-use">{s.use_vi}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
      <p className="lesson-foot">
        Sau phần bài học, {data.partner.toLowerCase()} sẽ hỏi bạn các câu liên quan. Hãy dùng lại những câu vừa học.
      </p>
    </main>
  );
}
