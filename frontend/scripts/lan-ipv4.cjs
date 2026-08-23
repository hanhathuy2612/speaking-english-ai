'use strict';

const DEFAULT_LAN_HOST = '192.168.1.100';

function pickLanIPv4() {
  const override = (process.env.DEV_LAN_HOST || '').trim();
  return override || DEFAULT_LAN_HOST;
}

module.exports = { pickLanIPv4 };

if (require.main === module) {
  process.stdout.write(pickLanIPv4());
}
