// Vérifie la construction et ajoute l'origine du back-end Amira (VITE_AMIRA_API_URL) aux
// autorisations du manifeste, pour que le service worker puisse l'appeler.
import { existsSync, readFileSync, writeFileSync } from 'node:fs';

function apiUrl() {
  if (process.env.VITE_AMIRA_API_URL) return process.env.VITE_AMIRA_API_URL;
  for (const f of ['.env.production.local', '.env.local', '.env.production', '.env']) {
    if (!existsSync(f)) continue;
    const m = readFileSync(f, 'utf8').match(/^\s*VITE_AMIRA_API_URL\s*=\s*(.*)$/m);
    if (m) return m[1].trim().replace(/^["']|["']$/g, '');
  }
  return '';
}

const m = JSON.parse(readFileSync('dist/manifest.json', 'utf8'));
const url = apiUrl();
if (url) {
  const u = new URL(url);
  const origin = `${u.protocol}//${u.host}/*`;
  if (!m.host_permissions.includes(origin)) m.host_permissions.push(origin);
  writeFileSync('dist/manifest.json', JSON.stringify(m, null, 2));
  console.log(`Back-end Amira : ${url}`);
} else {
  console.log(process.env.VITE_AMIRA_MODE === 'embedded' ? 'Mode autonome : mémoire validée et voix embarquées, sans serveur.' : 'Back-end Amira : non configuré → simulation (texte préfixé ⟦FF⟧). Voir .env.example.');
}
const files = [m.background.service_worker, m.side_panel.default_path, ...m.content_scripts.flatMap((c) => c.js), ...Object.values(m.icons)];
const missing = files.filter((f) => !existsSync(`dist/${f}`));
if (missing.length) {
  console.error('Fichiers manquants dans dist/ :', missing);
  process.exit(1);
}
console.log('dist/ prêt à charger dans chrome://extensions (mode développeur → Charger l\'extension non empaquetée).');
