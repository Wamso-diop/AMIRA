// Construit l'extension prête à charger pour le jury dans ../extension/, branchée sur le back-end local (demo.py).
// Usage : npm run jury [-- http://localhost:5000]   (la langue : VITE_AMIRA_LANGUAGE, défaut ff)
import { execSync } from 'node:child_process';
import { cpSync, rmSync } from 'node:fs';
import { resolve } from 'node:path';

const api = process.argv[2] || 'http://localhost:5000';
execSync('npm run build', { stdio: 'inherit', shell: true, env: { ...process.env, VITE_AMIRA_API_URL: api } });
rmSync('../extension', { recursive: true, force: true });
cpSync('dist', '../extension', { recursive: true });
console.log(`\nExtension prête : ${resolve('../extension')} (back-end : ${api})`);
