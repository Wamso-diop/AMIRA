// Construit l'extension prête à charger pour le jury dans ../extension/ : AUTONOME (mémoire validée et voix embarquées, elle agit seule)
// et HYBRIDE (si le back-end local lancé par demo.py répond, il traduit en plus ce que la mémoire ne connaît pas).
// Usage : npm run jury [-- http://localhost:5000]   (la langue : VITE_AMIRA_LANGUAGE, défaut ff)
import { execSync } from 'node:child_process';
import { cpSync, rmSync } from 'node:fs';
import { resolve } from 'node:path';

const api = process.argv[2] || 'http://localhost:5000';
execSync('npm run build', { stdio: 'inherit', shell: true, env: { ...process.env, VITE_AMIRA_API_URL: api, VITE_AMIRA_MODE: 'embedded' } });
rmSync('../extension', { recursive: true, force: true });
cpSync('dist', '../extension', { recursive: true });
console.log(`\nExtension prête : ${resolve('../extension')} (back-end : ${api})`);
