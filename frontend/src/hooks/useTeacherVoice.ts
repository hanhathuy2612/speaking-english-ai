import { useCallback, useEffect, useRef, useState } from "react";
import { authedAudio, playApi } from "../api/http";

/**
 * Plays a lesson's teacher lines one after another (GET <base>/audio/<key>, base = /api/lessons/<unit>
 * or /api/talks/<talk>).
 * One reused <audio> element: once it has played inside a tap, mobile browsers (iOS Safari in
 * particular) let it keep playing later lines that start outside a user gesture. The lines are
 * downloaded with the login token (api/http.ts), so the first tap plays a silent sound to unlock
 * the element before the download is done, and the next line is fetched while one plays.
 */
// A WAV file with no samples: playing it inside the first tap unlocks the element on mobile.
const SILENT = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=";

export function useTeacherVoice(base: string) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const queue = useRef<string[]>([]);
  const busy = useRef(false);
  const seq = useRef(0); // the line now playing; a stale play() rejection must not skip a line
  const [speaking, setSpeaking] = useState<string | null>(null);
  const unlocked = useRef(false);

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
    const url = (k: string) => `${base}/audio/${encodeURIComponent(k)}`;
    // A failed line must not block the ones after it; changing src rejects the previous play() too.
    void playApi(a, url(key), () => token === seq.current).catch(() => token === seq.current && playNext());
    if (queue.current[0]) void authedAudio(url(queue.current[0])).catch(() => {});
  }, [base]);

  useEffect(() => {
    const a = new Audio();
    const next = () => a.src !== SILENT && playNext(); // the unlock sound is not a line
    a.addEventListener("ended", next);
    a.addEventListener("error", next);
    audio.current = a;
    unlocked.current = false;
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
      const a = audio.current;
      if (a && !unlocked.current) {
        unlocked.current = true;
        a.src = SILENT;
        void a.play().catch(() => {});
      }
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
