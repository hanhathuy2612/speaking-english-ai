import { type PointerEvent, useCallback, useEffect, useRef, useState } from "react";

const MIN_BYTES = 3000; // shorter recordings are almost always an accidental tap

type Options = {
  onRecorded: (blob: Blob) => void;
  onStart?: () => void;
  onTooShort?: () => void;
  onError?: (message: string) => void;
  /** Hold Space to talk (ignored while typing in a form field). */
  spaceKey?: boolean;
};

/** Hold-to-talk microphone recording with MediaRecorder (webm/opus). */
export function useHoldToTalk({ onRecorded, onStart, onTooShort, onError, spaceKey = true }: Options) {
  const [recording, setRecording] = useState(false);
  const holding = useRef(false);
  const recorder = useRef<MediaRecorder | null>(null);
  // Keep the latest callbacks without re-binding listeners on every render.
  const cb = useRef({ onRecorded, onStart, onTooShort, onError });
  cb.current = { onRecorded, onStart, onTooShort, onError };

  const start = useCallback(async () => {
    if (holding.current) return;
    holding.current = true;
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
    } catch (err) {
      holding.current = false;
      cb.current.onError?.(err instanceof Error ? err.message : String(err));
    }
  }, []);

  const stop = useCallback(() => {
    holding.current = false;
    if (!recorder.current) return;
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

  /** Props for the mic button: press and hold, release (or leave) to stop. */
  const buttonProps = {
    onPointerDown: (e: PointerEvent) => {
      e.preventDefault();
      void start();
    },
    onPointerUp: stop,
    onPointerLeave: stop,
    onPointerCancel: stop,
  };

  return { recording, start, stop, buttonProps };
}
