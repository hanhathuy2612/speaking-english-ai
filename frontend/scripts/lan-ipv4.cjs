'use strict';

const os = require('os');

function score(ip) {
  if (ip.startsWith('192.168.')) return 0;
  if (ip.startsWith('10.')) return 1;
  if (/^172\.(1[6-9]|2\d|3[0-1])\./.test(ip)) return 2;
  return 9;
}

function pickLanIPv4() {
  const override = (process.env.DEV_LAN_HOST || '').trim();
  if (override) return override;

  const candidates = [];
  for (const addrs of Object.values(os.networkInterfaces())) {
    for (const addr of addrs || []) {
      const v4 = addr.family === 'IPv4' || addr.family === 4;
      if (!v4 || addr.internal) continue;
      if (addr.address.startsWith('169.254.')) continue;
      candidates.push(addr.address);
    }
  }

  candidates.sort((a, b) => score(a) - score(b));
  return candidates[0] || '127.0.0.1';
}

module.exports = { pickLanIPv4 };

if (require.main === module) {
  process.stdout.write(pickLanIPv4());
}
