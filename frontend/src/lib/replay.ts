/**
 * Playback of the learner's own recordings ("Nghe lại"). One shared player, so starting one
 * recording stops the previous one, and the microphone stops playback (useMic).
 * Recordings live only in the browser as object URLs (hooks/useRecordings.ts): nothing is uploaded
 * or stored for this, and they are gone after a page reload.
 */
let current: HTMLAudioElement | null = null;

/** Play `src`, stopping whatever was playing. Returns the element so callers can track its end. */
export function playReplay(src: string): HTMLAudioElement {
  stopReplay();
  const a = new Audio(src);
  current = a;
  void a.play().catch(() => a.dispatchEvent(new Event("ended")));
  return a;
}

export function stopReplay(): void {
  current?.pause();
  current = null;
}

/** An API result with the object URL of the recording it came from (client-side only). */
export type WithAudio<T> = T & { audio?: string };
