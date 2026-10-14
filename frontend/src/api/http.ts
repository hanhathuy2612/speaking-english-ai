/** Every backend call goes through here: the server's error message (Vietnamese, shown as is) becomes an
 * ApiError, and a 401 sends the app back to the login page, so no page handles an expired login itself.
 * Plain fetch is enough: the login is an HttpOnly cookie the browser sends on its own (no token to attach). */

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

/** Fired when the server says the login is gone (401 on an API call, or the WebSocket closed with 4401). */
export const AUTH_EXPIRED = "auth:expired";

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
  let r: Response;
  try {
    r = await fetch(url, init);
  } catch {
    throw new ApiError(0, "Không kết nối được máy chủ.");
  }
  // A wrong password on /api/auth/login is also a 401, but it is not an expired login.
  if (r.status === 401 && !url.startsWith("/api/auth/")) window.dispatchEvent(new Event(AUTH_EXPIRED));
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
