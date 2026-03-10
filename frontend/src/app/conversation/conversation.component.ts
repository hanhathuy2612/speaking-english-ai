import {
  Component,
  OnInit,
  OnDestroy,
  ViewChild,
  ElementRef,
  AfterViewChecked,
  ChangeDetectorRef,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { Subscription } from "rxjs";
import { WsService } from "../services/ws.service";
import { AudioService } from "../services/audio.service";

interface ChatMessage {
  role: "user" | "ai";
  text: string;
  partial?: boolean;
}

interface TurnScore {
  fluency: number;
  vocabulary: number;
  grammar: number;
  overall: number;
  feedback: string;
}

@Component({
  selector: "app-conversation",
  standalone: true,
  imports: [CommonModule, RouterLink],
  styleUrls: ["./conversation.component.scss"],
  templateUrl: "./conversation.component.html",
})
export class ConversationComponent
  implements OnInit, OnDestroy, AfterViewChecked
{
  @ViewChild("chatArea") private chatArea!: ElementRef<HTMLDivElement>;

  topicId = 0;
  topicTitle = "";
  connected = false;
  recording = false;
  aiSpeaking = false;
  ttsEnabled = true;
  vuLevel = 0;
  messages: ChatMessage[] = [];
  scores: Record<number, TurnScore> = {};

  private subs: Subscription[] = [];
  private pendingAiMsgIndex = -1;
  private audioQueue: ArrayBuffer[] = [];
  private playingAudio = false;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private ws: WsService,
    private audio: AudioService,
    private cdr: ChangeDetectorRef,
  ) {}

  ngOnInit(): void {
    this.route.queryParams.subscribe((p) => {
      this.topicId = Number(p["topicId"]) || 0;
      this.topicTitle = p["title"] ?? "Conversation";
    });

    // WS connected
    this.subs.push(
      this.ws.connected$.subscribe((c) => {
        this.connected = c;
        if (c) {
          this.ws.sendJson({ type: "start", topicId: this.topicId });
        }
        this.cdr.detectChanges();
      }),
    );

    // WS messages
    this.subs.push(
      this.ws.messages$.subscribe((msg) => {
        this._handleMessage(msg);
        this.cdr.detectChanges();
      }),
    );

    // Volume meter
    this.subs.push(
      this.audio.volume$.subscribe((v) => {
        this.vuLevel = v;
        this.cdr.detectChanges();
      }),
    );

    this.ws.connect(this.topicId);
  }

  ngAfterViewChecked(): void {
    this._scrollDown();
  }

  ngOnDestroy(): void {
    this.ws.sendJson({ type: "stop" });
    this.ws.disconnect();
    this.audio.release();
    this.subs.forEach((s) => s.unsubscribe());
  }

  toggleTts(): void {
    this.ttsEnabled = !this.ttsEnabled;
  }

  async startRecording(): Promise<void> {
    if (this.recording || !this.connected) return;
    this.recording = true;
    await this.audio.startRecording((buf) => this.ws.sendBinary(buf));
  }

  stopRecording(): void {
    if (!this.recording) return;
    this.recording = false;
    this.audio.stopRecording();
    this.ws.sendJson({ type: "audio_end" });
  }

  private _handleMessage(
    msg: Record<string, unknown> & { type: string },
  ): void {
    switch (msg["type"]) {
      case "user_transcript": {
        const text = msg["text"] as string;
        this.messages.push({ role: "user", text });
        this.pendingAiMsgIndex = -1;
        break;
      }
      case "assistant_partial": {
        const chunk = msg["text"] as string;
        const done = msg["done"] as boolean;
        if (this.pendingAiMsgIndex === -1) {
          this.messages.push({ role: "ai", text: chunk, partial: true });
          this.pendingAiMsgIndex = this.messages.length - 1;
        } else {
          this.messages[this.pendingAiMsgIndex].text += chunk;
        }
        if (done) {
          this.messages[this.pendingAiMsgIndex].partial = false;
          this.pendingAiMsgIndex = -1;
        }
        break;
      }
      case "assistant_audio_chunk": {
        if (!this.ttsEnabled) break;
        const b64 = msg["data"] as string;
        const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)).buffer;
        this.audioQueue.push(bytes);
        if (!this.playingAudio) this._flushAudioQueue();
        break;
      }
      case "turn_score": {
        // Attach score to the last user message
        const lastUserIdx = [...this.messages]
          .reverse()
          .findIndex((m) => m.role === "user");
        if (lastUserIdx !== -1) {
          const idx = this.messages.length - 1 - lastUserIdx;
          this.scores[idx] = {
            fluency: msg["fluency"] as number,
            vocabulary: msg["vocabulary"] as number,
            grammar: msg["grammar"] as number,
            overall: msg["overall"] as number,
            feedback: msg["feedback"] as string,
          };
        }
        break;
      }
    }
  }

  private async _flushAudioQueue(): Promise<void> {
    this.playingAudio = true;
    this.aiSpeaking = true;
    this.cdr.detectChanges();
    while (this.audioQueue.length > 0) {
      const chunk = this.audioQueue.shift()!;
      try {
        await this.audio.playAudioBuffer(chunk);
      } catch {
        // Ignore decode errors for partial chunks; they play fine when accumulated
      }
    }
    this.playingAudio = false;
    this.aiSpeaking = false;
    this.cdr.detectChanges();
  }

  private _scrollDown(): void {
    try {
      const el = this.chatArea?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    } catch {
      // ignore
    }
  }
}
