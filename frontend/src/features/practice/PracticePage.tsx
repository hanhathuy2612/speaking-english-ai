import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { AppBar } from "../../components/AppBar";
import { BookIcon, KeyboardIcon, MicIcon, TargetIcon } from "../../components/Icons";
import { Sheet } from "../../components/Sheet";
import { StatusLine } from "../../components/ui";
import { useMic } from "../../hooks/useMic";
import "../../styles/practice.css";
import { Chat } from "./Chat";
import { CoachCard } from "./CoachCard";
import { Sidebar } from "./Sidebar";
import { useInterview } from "./useInterview";

export function PracticePage() {
  const [params, setParams] = useSearchParams();
  const { state, actions } = useInterview(params.get("unit"));
  const { unit, progress, coach, shadow, retell } = state;
  const [typing, setTyping] = useState(false); // phones: the text box is hidden until asked for
  const [goals, setGoals] = useState(false); // phones: goal and phrases open in a bottom sheet
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    document.title = "Phòng tập nói";
  }, []);

  const mic = useMic({
    onStart: actions.stopAudio,
    onRecorded: actions.sendRecording,
    onTooShort: () => actions.setStatus({ text: "Ghi âm quá ngắn. Hãy nói hết câu rồi mới bấm dừng.", state: "warn" }),
    onError: (msg) => actions.setStatus({ text: `Không mở được micro: ${msg}`, state: "error" }),
  });

  useEffect(() => {
    if (mic.recording) actions.setStatus({ text: "Đang ghi âm… bấm lần nữa để gửi", state: "recording" });
  }, [mic.recording]); // only react to the recording flag; actions is a new object every render

  useEffect(() => {
    if (typing) input.current?.focus();
  }, [typing]);

  const onTyped = (e: KeyboardEvent<HTMLInputElement>) => {
    const text = e.currentTarget.value.trim();
    if (e.key !== "Enter" || !text) return;
    actions.sendText(text);
    e.currentTarget.value = "";
  };

  const done = progress ? (progress.done ? progress.n : progress.q - 1) : 0;
  const unitStatus = state.topics.flatMap((t) => t.units).find((u) => u.id === unit?.id);
  const lessonFirst = !!unit?.lesson && unitStatus?.lesson_done === 0;
  const phrases = unit?.phrases.length ?? 0;
  const sidebar = <Sidebar unit={unit} used={state.used} metrics={state.metrics} conf={state.conf} />;

  // "Nói lại câu này" / "Trả lời lại dài hơn" record right away: one tap instead of that button and then the mic.
  const beginShadow = () => {
    actions.beginShadow();
    if (!mic.recording) void mic.start();
  };
  const beginRetell = () => {
    actions.beginRetell();
    if (!mic.recording) void mic.start();
  };
  // Cancelling drops the recording: sent after the mode is cleared, it would count as a new answer.
  const cancelShadow = () => {
    mic.cancel();
    actions.cancelShadow();
  };
  const cancelRetell = () => {
    mic.cancel();
    actions.cancelRetell();
  };

  // While re-saying the note or answering again, the coach card may be scrolled away: keep the target in sight.
  const target = !coach
    ? null
    : shadow.waiting
      ? { label: "Đọc lại câu mẫu", text: coach.text, cancel: cancelShadow }
      : retell.waiting
        ? {
            label: "Trả lời lại, thêm các ý",
            text: (retell.result?.steps ?? coach.steps).map((st) => st.say).join("  ·  "),
            cancel: cancelRetell,
          }
        : null;
  const saying = !!target;
  useEffect(() => {
    if (saying) setTyping(false); // re-saying is spoken only (a typed message is always an answer)
  }, [saying]);

  return (
    <div className="app">
      <AppBar>
        <select
          className="select"
          aria-label="Chọn bài tập"
          value={state.unitId}
          onChange={(e) => {
            actions.startUnit(e.target.value);
            setParams({ unit: e.target.value }, { replace: true }); // reload keeps the same unit
          }}
        >
          {state.topics.map((t) => (
            // Locked stages stay selectable here (e.g. an interview coming up); the roadmap shows the lock.
            <optgroup key={t.id} label={t.locked ? `${t.title} (chưa mở)` : t.title}>
              {t.units.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.done ? "✓ " : ""}
                  {u.title}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        {unit?.lesson && (
          <Link className="btn btn-sm lesson-link" to={`/lesson/${encodeURIComponent(unit.id)}`}>
            <BookIcon size={15} />
            Bài giảng
          </Link>
        )}
        <div className={`progress${progress?.done ? " done" : ""}`}>
          <span className="progress-text" aria-live="polite">
            {progress &&
              (progress.done ? `Hoàn thành ${progress.n}/${progress.n}` : `Câu hỏi ${progress.q}/${progress.n}`)}
          </span>
          <div className="progress-bar" aria-hidden>
            <span style={{ width: progress ? `${(done / progress.n) * 100}%` : 0 }} />
          </div>
          <button
            className={`btn btn-sm goals-btn${phrases && state.used.length === phrases ? " all" : ""}`}
            onClick={() => setGoals(true)}
            aria-haspopup="dialog"
          >
            <TargetIcon />
            Mẫu câu {state.used.length}/{phrases}
          </button>
        </div>
        {unit?.stt && (
          <span className="chip stt-chip" title="Cấu hình nhận dạng giọng nói đang chạy">
            {unit.stt}
          </span>
        )}
      </AppBar>

      <div className="layout">
        {sidebar}

        <main className="stage">
          {lessonFirst && unit && (
            <div className="card lesson-first">
              <p>Bài này có bài giảng. Học trước để biết các câu nên dùng khi trả lời.</p>
              <Link className="btn btn-sm btn-primary" to={`/lesson/${encodeURIComponent(unit.id)}`}>
                <BookIcon size={15} />
                Học bài giảng
              </Link>
            </div>
          )}
          <Chat
            items={state.items}
            partner={unit?.partner ?? "Người phỏng vấn"}
            onUndo={state.canUndo ? actions.undo : undefined}
            tailKey={coach ? `${coach.text}|${!!shadow.result}|${!!retell.result}` : ""}
            tail={
              coach && (
                <CoachCard
                  coach={coach}
                  shadow={shadow}
                  onPlay={() => actions.playNote(coach.text)}
                  onShadow={beginShadow}
                  onCancelShadow={cancelShadow}
                  retell={retell}
                  onRetell={beginRetell}
                  onCancelRetell={cancelRetell}
                  mic={{ recording: mic.recording, busy: state.status.state === "busy", toggle: mic.toggle }}
                />
              )
            }
          />

          <div className="dock">
            {target && (
              <div className="dock-target">
                <div className="dock-target-text">
                  <span className="dock-target-label">{target.label}</span>
                  <span>{target.text}</span>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={target.cancel}>
                  Hủy
                </button>
              </div>
            )}
            <div className={`composer card${typing ? " typing" : ""}`}>
              <button
                className="icon-btn kbd-btn"
                aria-pressed={typing}
                aria-label="Gõ câu trả lời"
                onClick={() => setTyping((t) => !t)}
              >
                <KeyboardIcon />
              </button>
              <button
                className={`mic${mic.recording ? " rec" : ""}`}
                aria-label={mic.recording ? "Đang ghi âm, bấm để gửi" : "Bấm để nói"}
                {...mic.buttonProps}
              >
                <MicIcon />
              </button>
              <div className="composer-main">
                <input
                  ref={input}
                  className="input"
                  placeholder="Hoặc gõ câu trả lời rồi nhấn Enter"
                  autoComplete="off"
                  enterKeyHint="send"
                  aria-label="Gõ câu trả lời"
                  onKeyDown={onTyped}
                />
                <div className="composer-foot">
                  <StatusLine status={state.status} />
                  <span className="hint">Bấm micro để nói (hoặc giữ phím Space)</span>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>

      <Sheet open={goals} onClose={() => setGoals(false)} title={unit?.title ?? "Bài tập"}>
        {sidebar}
      </Sheet>
    </div>
  );
}
