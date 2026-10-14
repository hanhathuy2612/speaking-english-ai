/**
 * Playback of the learner's own recordings ("Nghe lại"). One shared player, so starting one
 * recording stops the previous one, and the microphone stops playback (useMic).
 * Recordings live only in the browser as object URLs (hooks/useRecordings.ts): nothing is uploaded
 * or stored for this, and they are gone after a page reload.
 *
 * Phone recordings are quiet (peaks around -18 to -27 dBFS measured), so playback goes through a
 * Web Audio gain that brings the peak near full scale (a 3x cap was tried and was too quiet).
 * Only playback changes: the recording sent for recognition is untouched.
 */
let current: HTMLAudioElement | null = null;
let ctx: AudioContext | null = null;
const gains = new Map<string, number>(); // src -> gain, computed once per recording

const TARGET_PEAK = 0.9; // about -1 dBFS
const MAX_GAIN = 12; // about +21 dB: louder would mostly raise room noise
const DEFAULT_GAIN = 4; // until the real peak is known (a few ms after start)

/** Gain that brings `peak` (0..1) to TARGET_PEAK, never quieter than as recorded, at most MAX_GAIN. */
export function replayGain(peak: number): number {
  if (!(peak > 0)) return 1;
  return Math.min(MAX_GAIN, Math.max(1, TARGET_PEAK / peak));
}

async function measure(src: string): Promise<number> {
  const data = await (await fetch(src)).arrayBuffer();
  const buf = await ctx!.decodeAudioData(data);
  let peak = 0;
  for (let c = 0; c < buf.numberOfChannels; c++) {
    for (const v of buf.getChannelData(c)) peak = Math.max(peak, Math.abs(v));
  }
  return replayGain(peak);
}

/** Play `src`, stopping whatever was playing. Returns the element so callers can track its end. */
export function playReplay(src: string): HTMLAudioElement {
  stopReplay();
  const a = new Audio(src);
  current = a;
  try {
    ctx ??= new AudioContext();
    void ctx.resume(); // inside the tap: allowed by mobile autoplay rules
    const gain = ctx.createGain();
    gain.gain.value = gains.get(src) ?? DEFAULT_GAIN;
    ctx.createMediaElementSource(a).connect(gain).connect(ctx.destination);
    if (!gains.has(src)) {
      measure(src)
        .then((g) => {
          gains.set(src, g);
          gain.gain.value = g;
        })
        .catch(() => {}); // keep the default gain
    }
  } catch {
    // no Web Audio: plain playback at the recorded level
  }
  void a.play().catch(() => a.dispatchEvent(new Event("ended")));
  return a;
}

export function stopReplay(): void {
  current?.pause();
  current = null;
}

/** An API result with the object URL of the recording it came from (client-side only). */
export type WithAudio<T> = T & { audio?: string };
