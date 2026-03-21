import type { CapacitorConfig } from '@capacitor/cli';

/**
 * Production / device build: `npm run android:build` (or `build:mobile` then `cap:sync` without dev URL).
 *
 * Live reload (dev, AVD):
 * Terminal 1 — `npm run start:android:emu`.
 * Terminal 2 — `npm run cap:run:android:dev:emu` (CLI `-l` injects live URL every run).
 * If you instead use `cap:sync`, set `CAPACITOR_DEV_SERVER_URL` (via `cap:sync:android:dev:emu`).
 * Before release: run `npm run cap:sync` (no dev URL), then `npm run android:build`.
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
