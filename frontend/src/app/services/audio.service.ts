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

    this.mediaRecorder = new MediaRecorder(this.stream!, { mimeType });
    this.mediaRecorder.ondataavailable = async (e) => {
      if (e.data.size > 0) {
        const buf = await e.data.arrayBuffer();
        onChunk(buf);
      }
    };
    this.mediaRecorder.start(200); // 200ms slices
  }

  stopRecording(): void {
    if (this.mediaRecorder?.state === 'recording') {
      this.mediaRecorder.stop();
    }
    this._stopVolume();
    if (this.audioCtx) {
      this.audioCtx.close();
      this.audioCtx = null;
    }
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

  /** Play PCM/MP3 bytes from ArrayBuffer */
  async playAudioBuffer(data: ArrayBuffer): Promise<void> {
    const ctx = new AudioContext();
    const buf = await ctx.decodeAudioData(data.slice(0));
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(ctx.destination);
    src.start();
  }

  release(): void {
    this.stopRecording();
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
  }
}
