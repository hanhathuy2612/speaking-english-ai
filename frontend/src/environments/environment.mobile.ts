import { LAN_HOST } from './lan-host';

/**
 * Packaged APK for a physical phone (same Wi‑Fi as this PC).
 * `npm run android:build` writes `lan-host.ts` from the current LAN IPv4.
 * Override: `DEV_LAN_HOST=192.168.x.x npm run android:build`
 */
export const environment = {
  production: true,
  apiBaseUrl: `http://${LAN_HOST}:8000/api/v1`,
  wsBaseUrl: `ws://${LAN_HOST}:8000/api/v1`,
};
