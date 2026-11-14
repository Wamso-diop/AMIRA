// Bout en bout (brief §6k) : la vraie extension (front/dist, construite avec VITE_AMIRA_API_URL) dans Chromium,
// branchée sur le vrai serveur. Vérifie : pastille « Prêt » sans « démo », traduction d'une page de test,
// lecture d'un message important. La page est servie par Playwright à l'adresse du site officiel
// (aucun accès réseau) ; ses textes français viennent du CSV gold (+ quelques phrases inconnues).
//
// Usage (voir tools/e2e_extension.sh) : node tools/e2e_extension.mjs http://localhost:5000
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const front = resolve(here, '../../front');
const { chromium } = createRequire(resolve(front, 'package.json'))('@playwright/test');
const API = process.argv[2] || 'http://localhost:5000';
const PAGE = 'https://safinum.cm/hackathon-test';

// CSV minimal (champs entre guillemets possibles)
function parseCsv(text) {
  const rows = [];
  let row = [], field = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(field); rows.push(row); row = []; field = '';
    } else field += c;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  const [head, ...body] = rows.filter((r) => r.length > 1);
  return body.map((r) => Object.fromEntries(head.map((h, i) => [h.replace(/^﻿/, ''), r[i] ?? ''])));
}

const gold = parseCsv(readFileSync(resolve(here, '../languages/ff/gold.csv'), 'utf8'));
const goldMessages = gold.filter((r) => r.kind === 'message').slice(0, 8).map((r) => r.fr.replace('{V1}', '5 000 FCFA'));
const unknown = ['Votre demande est en cours de traitement.', 'Le paiement sera disponible demain.',
  'Votre carte nécessite une vérification.', 'Consultez votre historique de transactions.'];
const html = `<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Banque test</title></head><body>
<h1>Espace client</h1>
${goldMessages.map((t) => `<p>${t}</p>`).join('\n')}
${unknown.map((t) => `<p>${t}</p>`).join('\n')}
<div role="alert">Attention : ne communiquez jamais votre code secret, même à un agent de la banque.</div>
</body></html>`;

const ext = resolve(front, 'dist');
const ctx = await chromium.launchPersistentContext(resolve(tmpdir(), `amira-e2e-${Date.now()}`), {
  channel: 'chromium',
  headless: !process.env.HEADED,
  args: [`--disable-extensions-except=${ext}`, `--load-extension=${ext}`],
});
await ctx.route(`${PAGE}*`, (route) => route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: html }));
let [sw] = ctx.serviceWorkers();
if (!sw) sw = await ctx.waitForEvent('serviceworker', { timeout: 15000 });
const extId = new URL(sw.url()).host;
await sw.evaluate(async () => chrome.storage.local.set({ 'amira.settings': { onboarded: true, prudence: false } }));

const report = { api: API, checks: {} };
const fail = (name, detail) => { report.checks[name] = { ok: false, detail }; };
const pass = (name, detail) => { report.checks[name] = { ok: true, detail }; };

// 1. pastille : état du service worker et texte visible du panneau
const panel = await ctx.newPage();
await panel.goto(`chrome-extension://${extId}/sidepanel.html`);
const status = await panel.evaluate(() => chrome.runtime.sendMessage({ type: 'amira:status' }));
await panel.waitForTimeout(1500);
const panelText = await panel.evaluate(() => document.body.innerText);
if (status?.state === 'ready' && status.demo === false && /Prêt/.test(panelText) && !/démo/i.test(panelText)) {
  pass('pastille', { state: status.state, demo: status.demo, capabilities: status.capabilities });
} else fail('pastille', { status, panelText: panelText.slice(0, 300) });

// 2. traduction de la page
const page = await ctx.newPage();
await page.goto(PAGE, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(1500);
const before = await page.evaluate(() => document.body.innerText);
const stats = await sw.evaluate(async (url) => {
  const [tab] = await chrome.tabs.query({ url: url + '*' });
  if (!tab?.id) return { error: 'onglet introuvable' };
  await chrome.tabs.sendMessage(tab.id, { type: 'amira:setEnabled', enabled: true });
  for (let i = 0; i < 80; i++) {
    await new Promise((r) => setTimeout(r, 250));
    const s = await chrome.tabs.sendMessage(tab.id, { type: 'amira:getStats' }, { frameId: 0 });
    if (s.total > 0 && s.pending === 0) return s;
  }
  return chrome.tabs.sendMessage(tab.id, { type: 'amira:getStats' }, { frameId: 0 });
}, PAGE);
const after = await page.evaluate(() => document.body.innerText);
const goldShown = gold.filter((r) => r.kind === 'message').slice(0, 8)
  .filter((r) => after.includes(r.ff.replace('{V1}', '5 000 FCFA'))).length;
const amountsKept = (after.match(/5 000 FCFA/g) ?? []).length === (before.match(/5 000 FCFA/g) ?? []).length;
if (stats.translated > 0 && stats.pending === 0 && goldShown > 0 && amountsKept && after !== before) {
  pass('traduction', { ...stats, goldShown, amountsKept });
} else fail('traduction', { stats, goldShown, amountsKept });

// 2b. message inédit (absent du gold) : traduit par le moteur, donc différent de l'original affiché avant
const inedit = unknown.filter((t) => before.includes(t) && !after.includes(t));
if (inedit.length > 0) pass('inedit', { traduits: inedit.length, sur: unknown.length });
else fail('inedit', { sur: unknown.length, note: 'aucune phrase inédite traduite' });

// 3. lecture des messages importants (comme l'onglet Voix) : une requête /v1/tts par passage.
// On lit le premier message ET l'avertissement (role=alert, « code secret »).
const readable = await sw.evaluate(async (url) => {
  const [tab] = await chrome.tabs.query({ url: url + '*' });
  return (await chrome.tabs.sendMessage(tab.id, { type: 'amira:readable', what: 'messages' }, { frameId: 0 })).segments;
}, PAGE);
const read = (s) => panel.evaluate((s) => chrome.runtime.sendMessage(
  { type: 'amira:tts', req: { text: s.text, language: 'fr', speed: 1, segmentKey: s.key } }), s);
const seg = readable[0];
const tts = seg && await read(seg);
if (tts?.ok && tts.data?.voice) pass('lecture', { key: seg.key, category: seg.category, voice: tts.data.voice });
else fail('lecture', { found: Boolean(seg), tts });
const warn = readable.find((s) => /code secret/i.test(s.text));
const ttsWarn = warn && await read(warn);
if (ttsWarn?.ok && ttsWarn.data?.voice) pass('avertissement', { category: warn.category, voice: ttsWarn.data.voice });
else fail('avertissement', { found: Boolean(warn), readable: readable.map((s) => s.category), ttsWarn });

await page.screenshot({ path: resolve(tmpdir(), 'amira-e2e.png'), fullPage: true });
await ctx.close();
writeFileSync(resolve(tmpdir(), 'amira-e2e.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
process.exit(Object.values(report.checks).every((c) => c.ok) ? 0 : 1);
