import { useCallback, useEffect, useRef } from "react";

type Item<M> = { meta: M; url: string };

/**
 * Plays MP3 chunks one after another. `onPlay(meta)` fires when an item *starts* playing,
 * which is when the practice page shows the interviewer's sentence (text follows the voice).
 */
export function useAudioQueue<M>(onPlay: (meta: M) => void) {
  const queue = useRef<Item<M>[]>([]);
  const playing = useRef(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const onPlayRef = useRef(onPlay);
  onPlayRef.current = onPlay;

  const playNext = useCallback(() => {
    const item = queue.current.shift();
    if (!item) {
      playing.current = false;
      return;
    }
    playing.current = true;
    onPlayRef.current(item.meta);
    const a = new Audio(item.url);
    audio.current = a;
    const done = () => {
      URL.revokeObjectURL(item.url);
      playNext();
    };
    a.onended = done;
    a.onerror = done;
    a.play().catch(done);
  }, []);

  const enqueue = useCallback(
    (meta: M, data: Blob | ArrayBuffer) => {
      const url = URL.createObjectURL(new Blob([data], { type: "audio/mpeg" }));
      queue.current.push({ meta, url });
      if (!playing.current) playNext();
    },
    [playNext],
  );

  const stop = useCallback(() => {
    queue.current.forEach((i) => URL.revokeObjectURL(i.url));
    queue.current = [];
    audio.current?.pause();
    audio.current = null;
    playing.current = false;
  }, []);

  useEffect(() => stop, [stop]);

  return { enqueue, stop, isPlaying: () => playing.current };
}
