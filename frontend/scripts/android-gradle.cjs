'use strict';

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const task = process.argv[2] || 'assembleDebug';
const androidDir = path.join(__dirname, '..', 'android');

function javaMajor(javaHome) {
  const java = path.join(javaHome, 'bin', process.platform === 'win32' ? 'java.exe' : 'java');
  if (!fs.existsSync(java)) return 0;
  const out = spawnSync(java, ['-version'], { encoding: 'utf8' });
  const text = `${out.stderr || ''}\n${out.stdout || ''}`;
  const m = text.match(/version "(\d+)/);
  return m ? Number(m[1]) : 0;
}

function findJdk21() {
  const candidates = [
    process.env.JAVA_HOME_21,
    'C:\\Program Files\\Amazon Corretto\\jdk21.0.12_9',
    process.env.JAVA_HOME,
  ].filter(Boolean);

  const correttoRoot = 'C:\\Program Files\\Amazon Corretto';
  if (fs.existsSync(correttoRoot)) {
    for (const dir of fs.readdirSync(correttoRoot)) {
      if (dir.toLowerCase().startsWith('jdk21')) {
        candidates.push(path.join(correttoRoot, dir));
      }
    }
  }

  for (const home of candidates) {
    if (javaMajor(home) >= 21) return home;
  }
  return null;
}

const jdk21 = findJdk21();
if (!jdk21) {
  console.error(
    '[android] JDK 21+ is required (Capacitor / AGP). Install Amazon Corretto 21 or set JAVA_HOME_21.',
  );
  process.exit(1);
}

const env = { ...process.env };
env.JAVA_HOME = jdk21;
env.PATH = path.join(jdk21, 'bin') + path.delimiter + env.PATH;
console.log(`[android] Using JDK ${javaMajor(jdk21)} at ${jdk21}`);

const gradlew = process.platform === 'win32' ? 'gradlew.bat' : './gradlew';
const result = spawnSync(gradlew, [task], {
  cwd: androidDir,
  env,
  stdio: 'inherit',
  shell: true,
});
process.exit(result.status ?? 1);
