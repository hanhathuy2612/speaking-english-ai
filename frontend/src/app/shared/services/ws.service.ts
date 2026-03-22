import { Injectable, NgZone, OnDestroy } from '@angular/core';
import { Subject } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from './auth.service';

export type WsMessage = Record<string, unknown> & { type: string };

const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000, 16000, 30000];
const MAX_RECONNECT_ATTEMPTS = 10;

@Injectable({ providedIn: 'root' })
export class WsService implements OnDestroy {
  private ws: WebSocket | null = null;
  private intentionalClose = false;
  private reconnectTopicId: number | null = null;
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  readonly messages$ = new Subject<WsMessage>();
  readonly connected$ = new Subject<boolean>();
  readonly reconnecting$ = new Subject<boolean>();

  constructor(
    private auth: AuthService,
    private zone: NgZone,
  ) {}

  connect(topicId: number): void {
    this.intentionalClose = false;
    this.reconnectTopicId = topicId;
    this.reconnectAttempt = 0;
    this._clearReconnectTimer();
    this.reconnecting$.next(false);
    this._doConnect(topicId);
  }

  private _doConnect(topicId: number): void {
    if (this.ws != null) {
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.close();
      this.ws = null;
    }
    const token = this.auth.getToken() ?? '';
    const wsBase =
      environment.wsBaseUrl ||
      (typeof location !== 'undefined'
        ? (location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host + '/api/v1'
        : '/api/v1');
    const url = `${wsBase}/ws/conversation?token=${encodeURIComponent(token)}&topic_id=${topicId}`;
    this.ws = new WebSocket(url);
    this.ws.binaryType = 'arraybuffer';

    this.ws.onopen = () =>
      this.zone.run(() => {
        this.reconnectAttempt = 0;
        this.reconnecting$.next(false);
        this.connected$.next(true);
      });

    this.ws.onclose = () =>
      this.zone.run(() => {
        this.ws = null;
        this.connected$.next(false);
        if (!this.intentionalClose && this.reconnectTopicId != null) {
          this._scheduleReconnect();
        }
      });

    this.ws.onerror = () => {
      // onclose will run after onerror; reconnect is handled there
    };

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

  private _clearReconnectTimer(): void {
    if (this.reconnectTimer != null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private _scheduleReconnect(): void {
    this._clearReconnectTimer();
    if (this.reconnectTopicId == null || this.reconnectAttempt >= MAX_RECONNECT_ATTEMPTS) {
      return;
    }
    const delay =
      RECONNECT_DELAYS_MS[Math.min(this.reconnectAttempt, RECONNECT_DELAYS_MS.length - 1)];
    this.reconnectAttempt += 1;
    this.reconnecting$.next(true);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.intentionalClose || this.reconnectTopicId == null) return;
      this._doConnect(this.reconnectTopicId);
    }, delay);
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
    this.intentionalClose = true;
    this.reconnectTopicId = null;
    this._clearReconnectTimer();
    this.reconnecting$.next(false);
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connected$.next(false);
  }

  isOpen(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Call before sending `{ type: 'stop' }` when the server will end the session and close the
   * socket, so the client does not treat the close as a network drop and auto-reconnect.
   */
  expectGracefulSessionShutdown(): void {
    this.intentionalClose = true;
  }

  ngOnDestroy(): void {
    this.disconnect();
  }
}
