import { devApiUrls } from './dev-host';
import { LAN_HOST } from './lan-host';

/**
 * Physical Android, live reload. API follows the page host when opened via LAN IP.
 * Packaged WebView is localhost, so fallback is `LAN_HOST` from `lan-host.ts`.
 */
const urls = devApiUrls(LAN_HOST);

export const environment = {
  production: false,
  apiBaseUrl: urls.apiBaseUrl,
  wsBaseUrl: urls.wsBaseUrl,
};
