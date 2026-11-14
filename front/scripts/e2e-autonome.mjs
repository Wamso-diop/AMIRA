// Test de bout en bout du mode AUTONOME : la vraie extension (extension/) dans Chromium, AUCUN serveur lancé.
// Vérifie : pastille « Prêt · autonome », page traduite par la mémoire validée, montants intacts, texte inconnu laissé en original,
// voix d'un natif jouée depuis le paquet, aucune requête vers l'extérieur. Usage (depuis front/, port 5000 libre) : node scripts/e2e-autonome.mjs
import { chromium } from '@playwright/test';
import { mkdtempSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { html } from './_demo-page.mjs';

const ext = resolve(process.env.AMIRA_EXT ?? '../extension'); // AMIRA_EXT : tester un dossier extrait (par exemple le ZIP à soumettre)
const PAGE = 'https://safinum.cm/hackathon-test';
const up = await fetch('http://localhost:5000/v1/health').then(() => true).catch(() => false);
if (up) { console.error('Un serveur répond sur le port 5000 : ce test doit tourner SANS serveur.'); process.exit(2); }

// libellés attendus : lus dans la mémoire validée (aucun mot de la langue écrit ici)
const gold = readFileSync(resolve('../backend/languages/ff/gold.csv'), 'utf8').split('\n');
const head = gold[0].split(',');
const csv = (l) => { const o = []; let f = '', q = false; for (const c of l) { if (c === '"') q = !q; else if (c === ',' && !q) { o.push(f); f = ''; } else f += c; } o.push(f); return o; };
const rows = gold.slice(1).filter(Boolean).map((l) => Object.fromEntries(csv(l).map((v, i) => [head[i], v])));
const ff = (fr) => rows.find((r) => r.fr.trim() === fr)?.ff.trim();

const ctx = await chromium.launchPersistentContext(mkdtempSync(resolve(tmpdir(), 'amira-auto-')), {
  channel: 'chromium', headless: true, args: [`--disable-extensions-except=${ext}`, `--load-extension=${ext}`],
});
const hosts = new Set();
ctx.on('request', (r) => { try { const u = new URL(r.url()); if (!['chrome-extension:', 'data:', 'blob:'].includes(u.protocol)) hosts.add(u.host); } catch { /* ignoré */ } });
await ctx.route(`${PAGE}*`, (r) => r.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: html }));
let [sw] = ctx.serviceWorkers();
if (!sw) sw = await ctx.waitForEvent('serviceworker', { timeout: 15000 });
const id = new URL(sw.url()).host;
await sw.evaluate(() => chrome.storage.local.set({ 'amira.settings': { onboarded: true, prudence: false } }));

const report = {};
const check = (name, ok, detail) => { report[name] = { ok: !!ok, detail }; };

const panel = await ctx.newPage();
await panel.goto(`chrome-extension://${id}/sidepanel.html`);
await panel.waitForTimeout(1200);
const status = await panel.evaluate(() => chrome.runtime.sendMessage({ type: 'amira:status' }));
await panel.waitForTimeout(500);
const pill = await panel.evaluate(() => document.querySelector('.etat')?.textContent ?? '');
check('pastille', status.state === 'ready' && status.demo === false && status.autonomous === true && /Prêt/.test(pill) && /autonome/.test(pill), { state: status.state, autonomous: status.autonomous, pill });

const page = await ctx.newPage();
await page.goto(PAGE, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(800);
const stats = await sw.evaluate(async (url) => {
  const [tab] = await chrome.tabs.query({ url: url + '*' });
  await chrome.tabs.sendMessage(tab.id, { type: 'amira:setEnabled', enabled: true });
  for (let i = 0; i < 60; i++) {
    await new Promise((r) => setTimeout(r, 250));
    const s = await chrome.tabs.sendMessage(tab.id, { type: 'amira:getStats' }, { frameId: 0 });
    if (s.total > 0 && s.pending === 0) return s;
  }
  return chrome.tabs.sendMessage(tab.id, { type: 'amira:getStats' }, { frameId: 0 });
}, PAGE);
const after = await page.evaluate(() => document.body.innerText);
const labels = ['Votre compte', 'Solde disponible', 'Effectuer un transfert', 'Total à débiter'];
const shown = labels.filter((l) => ff(l) && after.includes(ff(l)));
check('traduction par la mémoire', stats.translated > 0 && stats.errors === 0 && shown.length === labels.length, { translated: stats.translated, errors: stats.errors, libelles: `${shown.length}/${labels.length}` });
const amounts = ['250 000 FCFA', '25 500 FCFA', '500 FCFA', '+237 699 12 34 56'];
check('montants intacts', amounts.every((a) => after.includes(a)), amounts.map((a) => after.includes(a)));

// texte inconnu : sans serveur, l'original reste (jamais de traduction inventée)
const inconnu = 'Votre demande est en cours de traitement.';
await page.evaluate((t) => { const p = document.createElement('p'); p.textContent = t; document.querySelector('main').append(p); }, inconnu);
await page.waitForTimeout(2500);
check('texte inconnu laissé en original', (await page.evaluate(() => document.body.innerText)).includes(inconnu), inconnu);

// voix du natif depuis le paquet
const seg = await sw.evaluate(async (url) => {
  const [tab] = await chrome.tabs.query({ url: url + '*' });
  return (await chrome.tabs.sendMessage(tab.id, { type: 'amira:readable', what: 'page' }, { frameId: 0 })).segments;
}, PAGE);
let voices = 0;
for (const s of seg) {
  const r = await panel.evaluate((s) => chrome.runtime.sendMessage({ type: 'amira:tts', req: { text: s.text, language: 'ff', speed: 1, segmentKey: s.key } }), s);
  if (r?.ok && r.data.voice === 'recorded' && r.data.audioBase64?.length > 1000) voices++;
}
check('voix des natifs depuis le paquet', voices > 0, `${voices} passages de la page lus avec la voix d'un natif`);

const ext_hosts = [...hosts].filter((h) => h !== 'safinum.cm');
check('aucune requête vers l\'extérieur', ext_hosts.every((h) => h === 'localhost:5000'), ext_hosts);
await ctx.close();
console.log(JSON.stringify(report, null, 1));
process.exit(Object.values(report).every((c) => c.ok) ? 0 : 1);
