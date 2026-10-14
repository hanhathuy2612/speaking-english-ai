import { useCallback, useEffect, useRef, useState } from "react";
import { stopReplay } from "../lib/replay";

const MIN_BYTES = 3000; // shorter recordings are almost always an accidental tap

type Options = {
  onRecorded: (blob: Blob) => void;
  onStart?: () => void;
  onTooShort?: () => void;
  onError?: (message: string) => void;
  /** Hold Space to talk (ignored while typing in a form field). */
  spaceKey?: boolean;
};

/** A short vibration on phones that support it, so you feel recording start and stop. */
const buzz = (ms: number) => navigator.vibrate?.(ms);

/**
 * Microphone recording with MediaRecorder (webm/opus).
 * The button is tap to start, tap again to send (easier than holding on a phone); Space is still held to talk.
 */
export function useMic({ onRecorded, onStart, onTooShort, onError, spaceKey = true }: Options) {
  const [recording, setRecording] = useState(false);
  const holding = useRef(false);
  const recorder = useRef<MediaRecorder | null>(null);
  // Keep the latest callbacks without re-binding listeners on every render.
  const cb = useRef({ onRecorded, onStart, onTooShort, onError });
  cb.current = { onRecorded, onStart, onTooShort, onError };

  const start = useCallback(async () => {
    if (holding.current) return;
    holding.current = true;
    stopReplay(); // do not record your own playback
    cb.current.onStart?.();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!holding.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: rec.mimeType });
        if (blob.size < MIN_BYTES) cb.current.onTooShort?.();
        else cb.current.onRecorded(blob);
      };
      rec.start();
      recorder.current = rec;
      setRecording(true);
      buzz(30);
    } catch (err) {
      holding.current = false;
      cb.current.onError?.(err instanceof Error ? err.message : String(err));
    }
  }, []);

  const stop = useCallback(() => {
    holding.current = false;
    if (!recorder.current) return;
    buzz(15);
    recorder.current.stop();
    recorder.current = null;
    setRecording(false);
  }, []);

  useEffect(() => {
    if (!spaceKey) return;
    const typing = () => ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName ?? "");
    const down = (e: KeyboardEvent) => {
      if (e.code !== "Space" || e.repeat || typing()) return;
      e.preventDefault();
      void start();
    };
    const up = (e: KeyboardEvent) => {
      if (e.code !== "Space" || typing()) return;
      e.preventDefault();
      stop();
    };
    document.addEventListener("keydown", down);
    document.addEventListener("keyup", up);
    return () => {
      document.removeEventListener("keydown", down);
      document.removeEventListener("keyup", up);
    };
  }, [spaceKey, start, stop]);

  /** Tap to start, tap again to stop. A tap while the microphone is still opening cancels it. */
  const toggle = useCallback(() => (holding.current ? stop() : void start()), [start, stop]);
  const buttonProps = { onClick: toggle };

  return { recording, start, stop, toggle, buttonProps };
}
