// `npm run dev` : construit l'extension dans dist/, la reconstruit à chaque modification,
// et ouvre le guide animé qui montre comment la charger dans Chrome.
import { spawn } from 'node:child_process';
import { rmSync } from 'node:fs';
import { resolve } from 'node:path';

const vite = resolve('node_modules/vite/bin/vite.js');
const node = process.execPath;
const env = { ...process.env, VITE_DIST_PATH: resolve('dist') };
const children = [];

function run(args, { wait = true, label } = {}) {
  const child = spawn(node, [vite, ...args], { stdio: wait ? 'inherit' : ['ignore', 'pipe', 'inherit'], env });
  children.push(child);
  if (!wait) {
    child.stdout.on('data', (d) => {
      const txt = String(d);
      if (/built in|error/i.test(txt)) process.stdout.write(`[${label}] ${txt.trim().split('\n').pop()}\n`);
    });
    return child;
  }
  return new Promise((ok, ko) => child.on('exit', (c) => (c === 0 ? ok() : ko(new Error(`${label} a échoué`)))));
}

rmSync('dist', { recursive: true, force: true });
console.log('▶ Construction de dist/…');
await run(['build'], { label: 'panneau' });
await run(['build', '--config', 'vite.content.config.ts'], { label: 'contenu' });
await import('./build-manifest.mjs');

console.log('▶ Surveillance : dist/ se reconstruit à chaque modification (rechargez l’extension avec ↻ dans chrome://extensions).');
run(['build', '--watch'], { wait: false, label: 'panneau' });
run(['build', '--watch', '--config', 'vite.content.config.ts'], { wait: false, label: 'contenu' });

console.log('▶ Guide d’installation :');
const server = spawn(node, [vite, '--open', '/dev.html'], { stdio: 'inherit', env });
children.push(server);

const stop = () => {
  children.forEach((c) => c.kill());
  process.exit(0);
};
process.on('SIGINT', stop);
process.on('SIGTERM', stop);
