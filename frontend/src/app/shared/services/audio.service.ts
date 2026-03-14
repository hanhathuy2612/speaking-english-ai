import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AudioService {
  private mediaRecorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private audioCtx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private rafId: number | null = null;

  readonly chunk$ = new Subject<ArrayBuffer>();
  readonly volume$ = new Subject<number>(); // 0-100

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
  }

  /** Stops recording; when done, sends one full WebM blob via the callback, then resolves. Send audio_end after this. */
  stopRecording(): Promise<void> {
    return new Promise((resolve) => {
      const recorder = this.mediaRecorder;
      const onChunk = this.pendingOnChunk;
      this._stopVolume();
      if (this.audioCtx) {
        this.audioCtx.close();
        this.audioCtx = null;
      }
      if (!recorder || recorder.state !== 'recording') {
        resolve();
        return;
      }
      recorder.onstop = () => {
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

  /** Stop any currently playing audio (replay or TTS). Call before starting a new replay. */
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

  release(): void {
    this.stopRecording();
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
  }
}
