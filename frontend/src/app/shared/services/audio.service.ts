import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AudioService {
  private mediaRecorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private audioCtx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private rafId: number | null = null;
  private trackEndedListeners: Array<{ track: MediaStreamTrack; handler: () => void }> = [];

  readonly chunk$ = new Subject<ArrayBuffer>();
  readonly volume$ = new Subject<number>(); // 0-100
  /** Fires when the microphone track ends during recording (e.g. device switched). Call stopRecording + audio_end and clear stream for next recording. */
  readonly deviceLostDuringRecording$ = new Subject<void>();

  private recordedChunks: ArrayBuffer[] = [];
  private pendingOnChunk: ((buf: ArrayBuffer) => void) | null = null;

  async requestPermission(): Promise<boolean> {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      return true;
    } catch {
      return false;
    }
  }

  async startRecording(onChunk: (buf: ArrayBuffer) => void): Promise<void> {
    if (!this.stream) {
      const ok = await this.requestPermission();
      if (!ok) throw new Error('Microphone permission denied');
    }

    this.audioCtx = new AudioContext();
    const source = this.audioCtx.createMediaStreamSource(this.stream!);
    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = 256;
    source.connect(this.analyser);
    this._watchVolume();

    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm';

    this.recordedChunks = [];
    this.pendingOnChunk = onChunk;
    this.mediaRecorder = new MediaRecorder(this.stream!, { mimeType });
    this.mediaRecorder.ondataavailable = async (e) => {
      if (e.data.size > 0) {
        const buf = await e.data.arrayBuffer();
        this.recordedChunks.push(buf);
      }
    };
    this.mediaRecorder.start(200); // 200ms slices

    this._attachTrackEndedListeners();
  }

  private _attachTrackEndedListeners(): void {
    this._removeTrackEndedListeners();
    const stream = this.stream;
    if (!stream) return;
    const handler = (): void => {
      this._removeTrackEndedListeners();
      this._releaseStream();
      this.deviceLostDuringRecording$.next();
    };
    for (const track of stream.getAudioTracks()) {
      track.addEventListener('ended', handler);
      this.trackEndedListeners.push({ track, handler });
    }
  }

  private _removeTrackEndedListeners(): void {
    for (const { track, handler } of this.trackEndedListeners) {
      track.removeEventListener('ended', handler);
    }
    this.trackEndedListeners = [];
  }

  private _releaseStream(): void {
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
  }

  /** Stops recording; when done, sends one full WebM blob via the callback, then resolves. Send audio_end after this. */
  stopRecording(): Promise<void> {
    this._removeTrackEndedListeners();
    const recorder = this.mediaRecorder;
    const onChunk = this.pendingOnChunk;
    this._stopVolume();
    if (this.audioCtx) {
      this.audioCtx.close();
      this.audioCtx = null;
    }
    const flushChunks = (): void => {
      this.mediaRecorder = null;
      this.pendingOnChunk = null;
      const chunks = this.recordedChunks;
      this.recordedChunks = [];
      if (chunks.length > 0 && onChunk) {
        const total = chunks.reduce((s, c) => s + c.byteLength, 0);
        const out = new Uint8Array(total);
        let offset = 0;
        for (const c of chunks) {
          out.set(new Uint8Array(c), offset);
          offset += c.byteLength;
        }
        onChunk(out.buffer);
      }
    };
    if (!recorder) {
      flushChunks();
      return Promise.resolve();
    }
    if (recorder.state !== 'recording') {
      // Already stopped (e.g. track ended when device switched) — still flush so we send what we have
      flushChunks();
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      recorder.onstop = () => {
        flushChunks();
        resolve();
      };
      recorder.stop();
    });
  }

  private _watchVolume(): void {
    if (!this.analyser) return;
    const data = new Uint8Array(this.analyser.frequencyBinCount);
    const tick = () => {
      this.analyser!.getByteFrequencyData(data);
      const avg = data.reduce((s, v) => s + v, 0) / data.length;
      this.volume$.next(Math.min(100, Math.round((avg / 128) * 100)));
      this.rafId = requestAnimationFrame(tick);
    };
    this.rafId = requestAnimationFrame(tick);
  }

  private _stopVolume(): void {
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    this.volume$.next(0);
  }

  private playbackCtx: AudioContext | null = null;
  private playbackSource: AudioBufferSourceNode | null = null;

  /** Streaming TTS: one context, schedule chunks back-to-back for gapless playback */
  private streamingCtx: AudioContext | null = null;
  private streamingNextStart = 0;
  private streamingScheduledCount = 0;
  private streamingQueuedDecodes = 0;
  private streamingPendingBytes: Uint8Array | null = null;
  private streamingChain: Promise<void> = Promise.resolve();
  private streamingEndResolve: (() => void) | null = null;
  private streamingEndRequested = false;

  /** Stop any currently playing audio (replay or TTS). Also stops streaming playback. */
  stopPlayback(): void {
    if (this.playbackSource) {
      try {
        this.playbackSource.stop();
      } catch {
        // already stopped
      }
      this.playbackSource = null;
    }
    if (this.playbackCtx) {
      this.playbackCtx.close().catch(() => {});
      this.playbackCtx = null;
    }
    this._stopStreamingPlayback();
  }

  private _stopStreamingPlayback(): void {
    if (this.streamingCtx) {
      this.streamingCtx.close().catch(() => {});
      this.streamingCtx = null;
    }
    this.streamingNextStart = 0;
    this.streamingScheduledCount = 0;
    this.streamingQueuedDecodes = 0;
    this.streamingPendingBytes = null;
    this.streamingChain = Promise.resolve();
    this.streamingEndRequested = true;
    if (this.streamingEndResolve) {
      this.streamingEndResolve();
      this.streamingEndResolve = null;
    }
  }

  private _tryResolveStreamingEnd(): void {
    if (
      this.streamingEndRequested &&
      this.streamingScheduledCount <= 0 &&
      this.streamingQueuedDecodes <= 0 &&
      this.streamingEndResolve
    ) {
      const resolve = this.streamingEndResolve;
      this.streamingEndResolve = null;
      if (this.streamingCtx) {
        this.streamingCtx.close().catch(() => {});
        this.streamingCtx = null;
      }
      this.streamingNextStart = 0;
      this.streamingScheduledCount = 0;
      this.streamingQueuedDecodes = 0;
      this.streamingPendingBytes = null;
      this.streamingEndRequested = false;
      resolve();
    }
  }

  private _onStreamingChunkEnded(): void {
    this.streamingScheduledCount--;
    this._tryResolveStreamingEnd();
  }

  /**
   * Enqueue a TTS chunk for gapless streaming playback. Chunks are decoded and scheduled
   * back-to-back on one AudioContext so there are no gaps between chunks.
   */
  enqueueStreamingChunk(data: ArrayBuffer): void {
    if (!data?.byteLength) return;
    this.streamingQueuedDecodes++;
    this.streamingChain = this.streamingChain.then(async () => {
      if (!this.streamingCtx) {
        this.streamingCtx = new AudioContext();
        this.streamingNextStart = this.streamingCtx.currentTime;
        this.streamingEndRequested = false;
      }
      const ctx = this.streamingCtx;
      const incoming = new Uint8Array(data);
      let payload = incoming;
      const pending = this.streamingPendingBytes;
      if (pending) {
        const merged = new Uint8Array(pending.byteLength + incoming.byteLength);
        merged.set(pending);
        merged.set(incoming, pending.byteLength);
        payload = merged;
      }
      try {
        const buf = await ctx.decodeAudioData(payload.buffer.slice(0));
        this.streamingPendingBytes = null;
        const src = ctx.createBufferSource();
        src.buffer = buf;
        src.connect(ctx.destination);
        const lookaheadSec = 0.03;
        const startAt = Math.max(this.streamingNextStart, ctx.currentTime + lookaheadSec);
        this.streamingNextStart = startAt + buf.duration;
        this.streamingScheduledCount++;
        src.onended = () => this._onStreamingChunkEnded();
        src.start(startAt);
      } catch {
        // Chunk may be a partial frame; keep bytes and retry with the next chunk.
        this.streamingPendingBytes = payload;
      } finally {
        this.streamingQueuedDecodes--;
        this._tryResolveStreamingEnd();
      }
    });
  }

  /**
   * Call when no more TTS chunks will be sent. Returns a promise that resolves when all
   * scheduled chunks have finished playing.
   */
  endStreamingPlayback(): Promise<void> {
    this.streamingEndRequested = true;
    return new Promise<void>((resolve) => {
      this.streamingEndResolve = resolve;
      this._tryResolveStreamingEnd();
    });
  }

  /** Play one chunk; resolves when playback has finished. Stops any current playback first. */
  async playAudioBuffer(data: ArrayBuffer): Promise<void> {
    this.stopPlayback();
    const ctx = new AudioContext();
    this.playbackCtx = ctx;
    const buf = await ctx.decodeAudioData(data.slice(0));
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(ctx.destination);
    this.playbackSource = src;
    return new Promise((resolve) => {
      src.onended = () => {
        this.playbackSource = null;
        this.playbackCtx = null;
        ctx.close().catch(() => {});
        resolve();
      };
      src.start();
    });
  }

  /** Call when leaving conversation: stop playback, stop recording, release mic stream. */
  release(): void {
    this.stopPlayback();
    this._removeTrackEndedListeners();
    this.stopRecording();
    this._releaseStream();
  }
}
