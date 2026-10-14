import { useCallback, useEffect, useRef, useState } from "react";
import { stopReplay } from "../lib/replay";

const MIN_BYTES = 3000; // shorter recordings are almost always an accidental tap
/** Keep recording a little after the stop tap: people tap while still saying the last word. */
const TAIL_MS = 350;
/**
 * Plain microphone capture, like a phone's recorder app. With the browser defaults (echo cancellation,
 * noise suppression, auto gain) Chrome on Android records like a voice call: quiet (peaks around -18 to
 * -27 dBFS measured), noise suppression softens final /s/ /t/ (the very sounds the drills score), and an
 * open call-style microphone can lower playback volume. Echo cancellation is not needed: playback is
 * stopped whenever recording starts.
 */
const AUDIO: MediaTrackConstraints = { echoCancellation: false, noiseSuppression: false, autoGainControl: false };

type Options = {
  onRecorded: (blob: Blob) => void;
  /** Right at the tap, before the microphone is ready: stop playback, clear the last result. */
  onStart?: () => void;
  /** The recorder really runs: only now say "recording" and start a clock. */
  onRecording?: () => void;
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
 *
 * The microphone stays open while the page is visible: opening it takes a few hundred ms on a phone, and
 * words said in that time were lost (measured on drill recordings: the first words of a sentence missing).
 * `recording` only turns true once the recorder really runs, so the red button means "speak now".
 */
export function useMic({ onRecorded, onStart, onRecording, onTooShort, onError, spaceKey = true }: Options) {
  const [recording, setRecording] = useState(false);
  const holding = useRef(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const discard = useRef(false); // set by cancel(): the next stop drops the recording
  const stream = useRef<MediaStream | null>(null);
  // Keep the latest callbacks without re-binding listeners on every render.
  const cb = useRef({ onRecorded, onStart, onRecording, onTooShort, onError });
  cb.current = { onRecorded, onStart, onRecording, onTooShort, onError };

  const release = useCallback(() => {
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
  }, []);

  const openStream = useCallback(async () => {
    const live = stream.current?.getAudioTracks().some((t) => t.readyState === "live");
    if (!live) stream.current = await navigator.mediaDevices.getUserMedia({ audio: AUDIO });
    return stream.current!;
  }, []);

  const start = useCallback(async () => {
    if (holding.current) return;
    holding.current = true;
    stopReplay(); // do not record your own playback
    cb.current.onStart?.();
    try {
      const s = await openStream();
      if (!holding.current) return; // stopped while the microphone was opening
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
      const rec = new MediaRecorder(s, mime ? { mimeType: mime } : undefined);
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstart = () => {
        setRecording(true);
        buzz(30);
        cb.current.onRecording?.();
      };
      rec.onstop = () => {
        if (discard.current) {
          discard.current = false;
          return;
        }
        const blob = new Blob(chunks, { type: rec.mimeType });
        if (blob.size < MIN_BYTES) cb.current.onTooShort?.();
        else cb.current.onRecorded(blob);
      };
      rec.start();
      recorder.current = rec;
    } catch (err) {
      holding.current = false;
      cb.current.onError?.(err instanceof Error ? err.message : String(err));
    }
  }, [openStream]);

  const stop = useCallback(() => {
    holding.current = false;
    const rec = recorder.current;
    if (!rec) return;
    recorder.current = null;
    setRecording(false);
    buzz(15);
    setTimeout(() => rec.state !== "inactive" && rec.stop(), TAIL_MS);
  }, []);

  /** Stop without sending: the recording is dropped (a microphone still opening is simply abandoned). */
  const cancel = useCallback(() => {
    if (!holding.current) return;
    discard.current = !!recorder.current;
    stop();
  }, [stop]);

  // Close the microphone when the page is hidden (phone locked, another app) or left.
  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === "hidden" && !holding.current) release();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      release();
    };
  }, [release]);

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

  return { recording, start, stop, cancel, toggle, buttonProps };
}
