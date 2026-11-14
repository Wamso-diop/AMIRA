// Captures RÉELLES pour le dossier livrable : la vraie extension (extension/), branchée sur le vrai serveur (http://localhost:5000, lancé par
// `python demo.py`), traduit une page de démonstration bancaire reconstituée avec des libellés de l'environnement de test (mémoire validée).
// Usage (depuis front/, serveur lancé) : node scripts/livrable-capture.mjs  → docs/figures/real-*.png
import { chromium } from '@playwright/test';
import { mkdirSync, readFileSync, mkdtempSync } from 'node:fs';
import { resolve } from 'node:path';
import { tmpdir } from 'node:os';

const OUT = 'docs/figures';
const boxes = {};
mkdirSync(OUT, { recursive: true });
const ext = resolve('../extension');
const PAGE = 'https://safinum.cm/hackathon-test';
const ready = await fetch('http://localhost:5000/v1/ready').then((r) => r.status).catch(() => 0);
if (ready !== 200) { console.error('Serveur Amira non prêt (python demo.py) :', ready); process.exit(1); }

import { html } from './_demo-page.mjs';

const ctx = await chromium.launchPersistentContext(mkdtempSync(resolve(tmpdir(), 'amira-cap-')), {
  channel: 'chromium', headless: true, viewport: { width: 1180, height: 760 }, deviceScaleFactor: 2,
  args: [`--disable-extensions-except=${ext}`, `--load-extension=${ext}`],
});
await ctx.route(`${PAGE}*`, (r) => r.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: html }));
let [sw] = ctx.serviceWorkers();
if (!sw) sw = await ctx.waitForEvent('serviceworker', { timeout: 15000 });
const id = new URL(sw.url()).host;
await sw.evaluate(() => chrome.storage.local.set({ 'amira.settings': { onboarded: true, prudence: false } }));

const page = await ctx.newPage();
await page.goto(PAGE, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(800);
await page.screenshot({ path: `${OUT}/real-avant.png`, fullPage: true });

const panel = await ctx.newPage();
await panel.setViewportSize({ width: 400, height: 900 });
await panel.goto(`chrome-extension://${id}/sidepanel.html`);
await page.bringToFront();
await panel.waitForTimeout(1500);

const stats = await sw.evaluate(async (url) => {
  const [tab] = await chrome.tabs.query({ url: url + '*' });
  await chrome.tabs.sendMessage(tab.id, { type: 'amira:setEnabled', enabled: true });
  for (let i = 0; i < 80; i++) {
    await new Promise((r) => setTimeout(r, 250));
    const s = await chrome.tabs.sendMessage(tab.id, { type: 'amira:getStats' }, { frameId: 0 });
    if (s.total > 0 && s.pending === 0) return s;
  }
  return chrome.tabs.sendMessage(tab.id, { type: 'amira:getStats' }, { frameId: 0 });
}, PAGE);
console.log('stats', JSON.stringify(stats));
await page.waitForTimeout(600);
await page.screenshot({ path: `${OUT}/real-apres.png`, fullPage: true });

// moment « erreur » : un message d'erreur apparaît après coup, traduit et lu
await page.evaluate(() => { document.getElementById('err').style.display = 'block'; });
await page.waitForTimeout(2500);
await page.screenshot({ path: `${OUT}/real-erreur.png`, fullPage: true });

await panel.waitForTimeout(800);
// garde-fou : aucune clé de traduction brute (« translate.ff »…) ne doit s'afficher dans le panneau
const brutes = async (nom) => {
  const bad = await panel.evaluate(() => (document.body.innerText.match(/\b(app|states|translate|voice|settings|journal|onboarding)\.[A-Za-z][A-Za-z.]*/g) ?? []));
  if (bad.length) { console.error('CLÉS BRUTES dans', nom, bad); process.exitCode = 1; }
};
await brutes('Traduire');
const noteBox = async (tab, key, txt) => { const b = await panel.getByText(txt).first().boundingBox().catch(() => null); if (b) (boxes[tab] ??= {})[key] = b; };
for (const [k, t] of [['titre', 'Cette page'], ['bouton', 'Voir l’original'], ['compteurs', 'traduits'], ['options', 'Options de traduction'], ['fiabilite', 'Fiabilité'], ['rapide', 'Traducteur rapide']]) await noteBox('traduire', k, t);
await panel.screenshot({ path: `${OUT}/real-panneau-traduire.png`, fullPage: true });
for (const [name, file] of [['Voix', 'voix'], ['Journal', 'journal']]) {
  await panel.getByRole('tab', { name }).click().catch(() => panel.getByText(name, { exact: true }).first().click());
  await panel.waitForTimeout(700);
  await brutes(name);
  if (name === 'Voix') for (const [k, t] of [['titre', 'Écouter'], ['quelire', 'Que lire'], ['lecteur', 'Pause'], ['badge', 'Voix enregistrée'], ['vitesse', 'Vitesse'], ['auto', 'Lire automatiquement'], ['dictee', 'Dictée']]) await noteBox('voix', k, t);
  await panel.screenshot({ path: `${OUT}/real-panneau-${file}.png`, fullPage: true });
}
import('node:fs').then(({ writeFileSync }) => writeFileSync(`${OUT}/boxes.json`, JSON.stringify(boxes, null, 1)));
await ctx.close();
console.log('captures réelles écrites dans', OUT);
