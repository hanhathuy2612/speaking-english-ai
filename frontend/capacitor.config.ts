import type { CapacitorConfig } from '@capacitor/cli';

/**
 * Physical-device APK (default): `npm run android:build`
 *   writes the PC LAN IPv4 into lan-host.ts, then syncs Android.
 * Override: `DEV_LAN_HOST=192.168.x.x npm run android:build`
 * Emulator APK: `npm run android:build:emu` (API host 10.0.2.2).
 *
 * Live reload — physical phone (same Wi‑Fi):
 * Terminal 1 — `npm run start:android:device`.
 * Terminal 2 — `npm run cap:run:android:dev:device`.
 *
 * Live reload — emulator:
 * Terminal 1 — `npm run start:android:emu`.
 * Terminal 2 — `npm run cap:run:android:dev:emu`.
 */
const devServerUrl = process.env['CAPACITOR_DEV_SERVER_URL']?.trim();

const config: CapacitorConfig = {
  appId: 'com.speakai.app',
  appName: 'SpeakAI',
  webDir: 'dist/speakai/browser',
  android: {
    allowMixedContent: true,
  },
  ...(devServerUrl
    ? {
        server: {
          url: devServerUrl,
          cleartext: true,
        },
      }
    : {}),
};

export default config;
