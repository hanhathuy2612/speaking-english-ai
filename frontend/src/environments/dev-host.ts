/**
 * Host used to reach FastAPI from the page that is actually loaded.
 * Opening the app via LAN IP (phone browser or Capacitor live reload) must not
 * keep calling `localhost` — that is the phone, not the PC.
 */
export function resolveDevApiHost(fallback = 'localhost'): string {
  if (typeof location === 'undefined') {
    return fallback;
  }
  const host = location.hostname?.trim();
  if (!host || host === 'localhost' || host === '127.0.0.1') {
    return fallback;
  }
  return host;
}

export function devApiUrls(fallbackHost = 'localhost'): {
  apiBaseUrl: string;
  wsBaseUrl: string;
} {
  const host = resolveDevApiHost(fallbackHost);
  return {
    apiBaseUrl: `http://${host}:8000/api/v1`,
    wsBaseUrl: `ws://${host}:8000/api/v1`,
  };
}
