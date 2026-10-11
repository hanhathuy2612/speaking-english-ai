import { type KeyboardEvent, useEffect } from "react";
import { useSearchParams } from "react-router";
import { AppBar } from "../../components/AppBar";
import { MicIcon, UndoIcon } from "../../components/Icons";
import { StatusLine } from "../../components/ui";
import { useHoldToTalk } from "../../hooks/useHoldToTalk";
import "../../styles/practice.css";
import { Chat } from "./Chat";
import { CoachCard } from "./CoachCard";
import { Sidebar } from "./Sidebar";
import { useInterview } from "./useInterview";

export function PracticePage() {
  const [params, setParams] = useSearchParams();
  const { state, actions } = useInterview(params.get("unit"));
  const { unit, progress, coach, shadow } = state;

  useEffect(() => {
    document.title = "Phòng tập nói";
  }, []);

  const mic = useHoldToTalk({
    onStart: actions.stopAudio,
    onRecorded: actions.sendRecording,
    onTooShort: () => actions.setStatus({ text: "Ghi âm quá ngắn. Hãy giữ nút lâu hơn.", state: "warn" }),
    onError: (msg) => actions.setStatus({ text: `Không mở được micro: ${msg}`, state: "error" }),
  });

  useEffect(() => {
    if (mic.recording) actions.setStatus({ text: "Đang ghi âm… thả ra để gửi", state: "recording" });
  }, [mic.recording]); // only react to the recording flag; actions is a new object every render

  const onTyped = (e: KeyboardEvent<HTMLInputElement>) => {
    const text = e.currentTarget.value.trim();
    if (e.key !== "Enter" || !text) return;
    actions.sendText(text);
    e.currentTarget.value = "";
  };

  const done = progress ? (progress.done ? progress.n : progress.q - 1) : 0;

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
                  {u.completed ? "✓ " : ""}
                  {u.title}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <div className={`progress${progress?.done ? " done" : ""}`} aria-live="polite">
          <span className="progress-text">
            {progress && (progress.done ? `Hoàn thành ${progress.n}/${progress.n}` : `Câu hỏi ${progress.q}/${progress.n}`)}
          </span>
          <div className="progress-bar" aria-hidden>
            <span style={{ width: progress ? `${(done / progress.n) * 100}%` : 0 }} />
          </div>
        </div>
        {unit?.stt && (
          <span className="chip stt-chip" title="Cấu hình nhận dạng giọng nói đang chạy">
            {unit.stt}
          </span>
        )}
      </AppBar>

      <div className="layout">
        <Sidebar unit={unit} used={state.used} metrics={state.metrics} conf={state.conf} />

        <main className="stage">
          <Chat items={state.items} partner={unit?.partner ?? "Người phỏng vấn"} />

          <div className="dock">
            {coach && (
              <CoachCard
                coach={coach}
                shadow={shadow}
                onPlay={() => actions.playNote(coach.text)}
                onShadow={actions.beginShadow}
                onCancelShadow={actions.cancelShadow}
              />
            )}

            <div className="composer card">
              <button
                className={`mic${mic.recording ? " rec" : ""}`}
                aria-label={mic.recording ? "Đang ghi âm, thả ra để gửi" : "Giữ để nói"}
                {...mic.buttonProps}
              >
                <MicIcon />
              </button>
              <div className="composer-main">
                <div className="composer-row">
                  <input
                    className="input"
                    placeholder="Hoặc gõ câu trả lời rồi nhấn Enter"
                    autoComplete="off"
                    aria-label="Gõ câu trả lời"
                    onKeyDown={onTyped}
                  />
                  {state.canUndo && (
                    <button className="btn btn-ghost btn-sm" onClick={actions.undo}>
                      <UndoIcon />
                      Máy nghe sai, nói lại
                    </button>
                  )}
                </div>
                <div className="composer-foot">
                  <StatusLine status={state.status} />
                  <span className="hint">Giữ nút micro hoặc phím Space để nói</span>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
