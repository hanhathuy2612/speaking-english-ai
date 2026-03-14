import { Injectable, NgZone, OnDestroy } from '@angular/core';
import { Subject } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from './auth.service';

export type WsMessage = Record<string, unknown> & { type: string };

@Injectable({ providedIn: 'root' })
export class WsService implements OnDestroy {
  private ws: WebSocket | null = null;
  readonly messages$ = new Subject<WsMessage>();
  readonly connected$ = new Subject<boolean>();

  constructor(
    private auth: AuthService,
    private zone: NgZone,
  ) {}

  connect(topicId: number): void {
    this.disconnect();
    const token = this.auth.getToken() ?? '';
    const url = `${environment.wsBaseUrl}/ws/conversation?token=${encodeURIComponent(token)}&topic_id=${topicId}`;
    this.ws = new WebSocket(url);
    this.ws.binaryType = 'arraybuffer';

    this.ws.onopen = () => this.zone.run(() => this.connected$.next(true));
    this.ws.onclose = () => this.zone.run(() => this.connected$.next(false));
    this.ws.onmessage = (ev) => {
      this.zone.run(() => {
        if (typeof ev.data === 'string') {
          try {
            const msg = JSON.parse(ev.data) as WsMessage;
            this.messages$.next(msg);
          } catch {
            // ignore
          }
        }
      });
    };
  }

  sendJson(data: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  sendBinary(data: ArrayBuffer | Uint8Array): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(data);
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  isOpen(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  ngOnDestroy(): void {
    this.disconnect();
  }
}
