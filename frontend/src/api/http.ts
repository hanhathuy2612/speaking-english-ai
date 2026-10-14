/** JSON calls to the backend with the error message the server wrote (Vietnamese, shown as is). */

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

export async function api<T>(url: string, init?: { method?: string; body?: unknown }): Promise<T> {
  const r = await fetch(url, {
    method: init?.method ?? (init?.body === undefined ? "GET" : "POST"),
    headers: init?.body === undefined ? undefined : { "Content-Type": "application/json" },
    body: init?.body === undefined ? undefined : JSON.stringify(init.body),
  });
  const body = await r.json().catch(() => null);
  if (!r.ok) throw errorOf(r.status, body);
  return body as T;
}

/** Fired when the server says the login is gone (401 on an API call, or the WebSocket closed with 4401). */
export const AUTH_EXPIRED = "auth:expired";

/** Watch every API response once, so a page never has to handle an expired login itself. */
export function watchExpiredLogin() {
  const original = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const r = await original(input, init);
    const url = typeof input === "string" ? input : input instanceof URL ? input.pathname : input.url;
    const path = new URL(url, location.origin).pathname;
    if (r.status === 401 && path.startsWith("/api/") && !path.startsWith("/api/auth/")) {
      window.dispatchEvent(new Event(AUTH_EXPIRED));
    }
    return r;
  };
}
