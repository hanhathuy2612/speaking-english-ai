/** Every backend call goes through here (docs/features/accounts.md): the server's error message
 * (Vietnamese, shown as is) becomes an ApiError, and the login travels as `Authorization: Bearer <JWT>`.
 *
 * The access token lives 15 minutes, the refresh token 30 days, both in localStorage. A call made
 * with an expired access token first gets a new one from /api/auth/refresh; when that fails too the
 * login is gone, the tokens are forgotten and the app goes back to the login page. */
import type { User } from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly code?: string,
    readonly errors: string[] = [], // itemized problems, e.g. an invalid unit (code "invalid")
  ) {
    super(message);
  }
}

/** Fired when the login is gone (refresh refused, or the WebSocket closed with 4401). */
export const AUTH_EXPIRED = "auth:expired";

/** What logging in answers: /api/auth/login, /verify, /reset, /refresh, /password. */
export type LoginAnswer = { user: User; access_token: string; refresh_token: string; expires_in: number };

const ACCESS = "auth.access";
const REFRESH = "auth.refresh";
// Calls that log in or work logged out: no token sent, and a 401 there is an answer (wrong password).
const LOGGED_OUT = /^\/api\/auth\/(login|refresh|signup|resend|verify|forgot|reset)$/;

function load(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function store(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // private mode with storage blocked: the login lasts until the page is reloaded
  }
}

let memory: { access: string | null; refresh: string | null } = { access: load(ACCESS), refresh: load(REFRESH) };

/** Keep the tokens of a login answer; returns its user. */
export function saveLogin(answer: LoginAnswer): User {
  memory = { access: answer.access_token, refresh: answer.refresh_token };
  store(ACCESS, memory.access);
  store(REFRESH, memory.refresh);
  return answer.user;
}

/** Logging out: the tokens are stateless, so forgetting them is all there is to do. */
export function forgetLogin(): void {
  memory = { access: null, refresh: null };
  store(ACCESS, null);
  store(REFRESH, null);
  audio.forEach((p) => void p.then(URL.revokeObjectURL, () => {}));
  audio.clear();
  ready.clear();
}

export function hasLogin(): boolean {
  return !!(memory.refresh ?? load(REFRESH));
}

/** Seconds since 1970 when a JWT expires (read without checking the signature: the server does that). */
function expiry(token: string): number {
  try {
    return JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))).exp ?? 0;
  } catch {
    return 0;
  }
}

let refreshing: Promise<string | null> | null = null;

async function refresh(): Promise<string | null> {
  const token = memory.refresh ?? load(REFRESH); // another tab may have refreshed already
  if (!token) return null;
  let r: Response;
  try {
    r = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: token }),
    });
  } catch {
    throw new ApiError(0, "Không kết nối được máy chủ.");
  }
  if (!r.ok) return null;
  saveLogin(await r.json());
  return memory.access;
}

/** A valid access token, refreshed when it expires within 30 s; null when the login is gone. Several
 * calls at once share one refresh. */
export async function accessToken(force = false): Promise<string | null> {
  const t = memory.access ?? load(ACCESS);
  if (t && !force && expiry(t) - Date.now() / 1000 > 30) return t;
  refreshing ??= refresh().finally(() => (refreshing = null));
  return refreshing;
}

function expired(): ApiError {
  forgetLogin();
  window.dispatchEvent(new Event(AUTH_EXPIRED));
  return new ApiError(401, "Phiên đăng nhập đã hết. Hãy đăng nhập lại.");
}

async function call(url: string, init: RequestInit): Promise<Response> {
  const open = LOGGED_OUT.test(url.split("?")[0]);
  const attempt = async (token: string | null) => {
    try {
      return await fetch(url, {
        ...init,
        headers: {
          ...(init.headers as Record<string, string>),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });
    } catch {
      throw new ApiError(0, "Không kết nối được máy chủ.");
    }
  };
  if (open) return attempt(null);
  const token = await accessToken();
  if (!token) throw expired();
  const r = await attempt(token);
  if (r.status !== 401) return r;
  const fresh = await accessToken(true); // the server refused it early (key changed, clock skew)
  if (!fresh) throw expired();
  const again = await attempt(fresh);
  if (again.status === 401) throw expired();
  return again;
}

/** FastAPI errors: {"detail": "text"} or {"detail": {"code", "msg", "errors"?}} (validation errors are a list). */
function errorOf(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return new ApiError(status, detail);
  if (detail && typeof detail === "object" && "msg" in detail) {
    const d = detail as { msg: string; code?: string; errors?: string[] };
    return new ApiError(status, d.msg, d.code, d.errors);
  }
  return new ApiError(status, status === 422 ? "Dữ liệu chưa hợp lệ." : `Lỗi máy chủ (${status}).`);
}

async function send<T>(url: string, init: RequestInit): Promise<T> {
  const r = await call(url, init);
  const body = await r.json().catch(() => null);
  if (!r.ok) throw errorOf(r.status, body);
  return body as T;
}

/** JSON call: GET without a body, POST with one, unless `method` says otherwise. */
export function api<T = unknown>(url: string, init?: { method?: string; body?: unknown }): Promise<T> {
  const hasBody = init?.body !== undefined;
  return send<T>(url, {
    method: init?.method ?? (hasBody ? "POST" : "GET"),
    headers: hasBody ? { "Content-Type": "application/json" } : undefined,
    body: hasBody ? JSON.stringify(init!.body) : undefined,
  });
}

/** POST raw audio (a recording) and read the JSON answer. */
export function postAudio<T = unknown>(url: string, blob: Blob): Promise<T> {
  return send<T>(url, { method: "POST", body: blob });
}

// <audio src> cannot send a header, so API audio is downloaded with the token and played as an object
// URL. Kept for the page's lifetime (a lesson replays the same lines); forgotten on logout.
const audio = new Map<string, Promise<string>>();
const ready = new Map<string, string>();

/** Object URL of an audio file behind the login (/api/...); other URLs (blob:) are returned as is. */
export function authedAudio(url: string): Promise<string> {
  if (!url.startsWith("/api/")) return Promise.resolve(url);
  let p = audio.get(url);
  if (!p) {
    p = call(url, { method: "GET" }).then(async (r) => {
      if (!r.ok) throw errorOf(r.status, null);
      const src = URL.createObjectURL(await r.blob());
      ready.set(url, src);
      return src;
    });
    p.catch(() => audio.delete(url)); // a failed download is tried again next time
    audio.set(url, p);
  }
  return p;
}

/** The object URL when `url` is already downloaded, so a tap can start playing without waiting. */
export function readyAudio(url: string): string | undefined {
  return url.startsWith("/api/") ? ready.get(url) : url;
}

/** Play API audio in `a`: at once when already downloaded (still inside the tap), otherwise after the
 * download, unless `still()` says the player moved on meanwhile. */
export async function playApi(a: HTMLAudioElement, url: string, still: () => boolean = () => true): Promise<void> {
  const now = readyAudio(url);
  if (now) {
    a.src = now;
    return a.play();
  }
  const src = await authedAudio(url);
  if (!still()) return;
  a.src = src;
  return a.play();
}
