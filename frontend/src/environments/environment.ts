import { devApiUrls } from './dev-host';

const urls = devApiUrls();

export const environment = {
  production: false,
  apiBaseUrl: urls.apiBaseUrl,
  wsBaseUrl: urls.wsBaseUrl,
};
