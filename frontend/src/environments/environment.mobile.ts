/**
 * Manual checks on device/emulator: conversation WebSocket, microphone grant/deny flows,
 * route refresh (PathLocationStrategy + base href).
 */
export const environment = {
  production: true,
  /**
   * Android emulator: `10.0.2.2` is the host machine’s loopback.
   * Physical device: set to your PC’s LAN IP (same Wi‑Fi), e.g. http://192.168.1.10:8000/api/v1
   *
   * Ensure the FastAPI backend allows this app’s WebView origin in CORS (often http/https localhost
   * or capacitor:// — check Capacitor docs for your version).
   */
  apiBaseUrl: 'http://10.0.2.2:8000/api/v1',
  wsBaseUrl: 'ws://10.0.2.2:8000/api/v1',
};
