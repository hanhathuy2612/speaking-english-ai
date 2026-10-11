import { useEffect, useRef, useState } from "react";
import { playReplay, stopReplay } from "../lib/replay";
import { PlayIcon, StopIcon } from "./Icons";

/** "Nghe lại": play back the learner's own recording (lib/replay.ts). */
export function ReplayButton({ src, label = "Nghe lại" }: { src?: string; label?: string }) {
  const [playing, setPlaying] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);

  useEffect(
    () => () => {
      if (audio.current) stopReplay();
    },
    [],
  );

  if (!src) return null;
  const toggle = () => {
    if (playing) {
      stopReplay();
      return;
    }
    const a = playReplay(src);
    audio.current = a;
    setPlaying(true);
    const done = () => {
      setPlaying(false);
      if (audio.current === a) audio.current = null;
    };
    a.addEventListener("ended", done);
    a.addEventListener("pause", done); // stopped, or replaced by another recording
  };
  return (
    <button
      type="button"
      className={`btn btn-ghost replay${playing ? " playing" : ""}`}
      onClick={toggle}
      aria-label={playing ? "Dừng phát giọng bạn" : "Nghe lại giọng bạn"}
      title="Nghe lại giọng bạn"
    >
      {playing ? <StopIcon size={12} /> : <PlayIcon size={12} />}
      {label}
    </button>
  );
}
