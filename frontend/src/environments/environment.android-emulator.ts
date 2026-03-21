/**
 * Use with `npm run start:android:emu` when the WebView loads `ng serve` via Capacitor
 * (`cap:sync:android:dev:emu`). `localhost` here would mean the emulator, not your PC.
 */
export const environment = {
  production: false,
  apiBaseUrl: 'http://10.0.2.2:8000/api/v1',
  wsBaseUrl: 'ws://10.0.2.2:8000/api/v1',
};
