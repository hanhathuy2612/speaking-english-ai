import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Plays a lesson's teacher lines one after another (GET /api/lessons/<unit>/audio/<key>).
 * One reused <audio> element: once it has played inside a tap, mobile browsers (iOS Safari in
 * particular) let it keep playing later lines that start outside a user gesture.
 */
export function useTeacherVoice(unitId: string) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const queue = useRef<string[]>([]);
  const busy = useRef(false);
  const seq = useRef(0); // the line now playing; a stale play() rejection must not skip a line
  const [speaking, setSpeaking] = useState<string | null>(null);

  const playNext = useCallback(() => {
    const key = queue.current.shift();
    const a = audio.current;
    if (!key || !a) {
      busy.current = false;
      setSpeaking(null);
      return;
    }
    busy.current = true;
    setSpeaking(key);
    const token = ++seq.current;
    a.src = `/api/lessons/${encodeURIComponent(unitId)}/audio/${encodeURIComponent(key)}`;
    // A failed line must not block the ones after it; changing src rejects the previous play() too.
    void a.play().catch(() => token === seq.current && playNext());
  }, [unitId]);

  useEffect(() => {
    const a = new Audio();
    const next = () => playNext();
    a.addEventListener("ended", next);
    a.addEventListener("error", next);
    audio.current = a;
    return () => {
      a.pause();
      a.removeEventListener("ended", next);
      a.removeEventListener("error", next);
      audio.current = null;
      queue.current = [];
      busy.current = false;
    };
  }, [playNext]);

  /** Queue lines after the ones already playing. */
  const enqueue = useCallback(
    (keys: string[]) => {
      queue.current.push(...keys);
      if (!busy.current) playNext();
    },
    [playNext],
  );

  const stop = useCallback(() => {
    seq.current++;
    queue.current = [];
    audio.current?.pause();
    busy.current = false;
    setSpeaking(null);
  }, []);

  /** Play one line now, dropping whatever was queued (the speaker buttons). */
  const playNow = useCallback(
    (key: string) => {
      stop();
      enqueue([key]);
    },
    [stop, enqueue],
  );

  return { enqueue, stop, playNow, speaking };
}
