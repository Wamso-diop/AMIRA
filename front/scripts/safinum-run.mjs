// Lance l'extension construite (dist/) dans Chromium sur l'environnement de test officiel,
// active la traduction (mode démonstration) et mesure le résultat.
// Usage : npm run safinum   (options : SAFINUM_URL=…  HEADED=1)
import { chromium } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { tmpdir } from 'node:os';

const URL_TEST = process.env.SAFINUM_URL || 'https://safinum.cm/hackathon-test';
const ext = resolve('dist');
const profile = resolve(tmpdir(), `amira-profile-${Date.now()}`);
mkdirSync('tests/e2e/results', { recursive: true });

const ctx = await chromium.launchPersistentContext(profile, {
  channel: 'chromium',
  headless: !process.env.HEADED,
  args: [`--disable-extensions-except=${ext}`, `--load-extension=${ext}`],
});

let [sw] = ctx.serviceWorkers();
if (!sw) sw = await ctx.waitForEvent('serviceworker', { timeout: 15000 });

// Mode démonstration : aucun serveur réel requis.
await sw.evaluate(async () => {
  await chrome.storage.local.set({ 'amira.settings': { onboarded: true, demoMode: true, mockScenario: 'normal', prudence: false } });
});

const page = await ctx.newPage();
const t0 = Date.now();
try {
  await page.goto(URL_TEST, { waitUntil: 'domcontentloaded', timeout: 30000 });
} catch (e) {
  console.error(`Impossible d'ouvrir ${URL_TEST} : ${e.message}`);
  await ctx.close();
  process.exit(2);
}
await page.waitForTimeout(1500);

const stats = await sw.evaluate(async (url) => {
  const [tab] = await chrome.tabs.query({ url: url.replace(/[?#].*$/, '') + '*' });
  if (!tab?.id) return { error: 'onglet introuvable' };
  try {
    await chrome.tabs.sendMessage(tab.id, { type: 'amira:setEnabled', enabled: true });
  } catch {
    return { error: 'script de contenu absent (vérifier host_permissions)' };
  }
  for (let i = 0; i < 60; i++) {
    await new Promise((r) => setTimeout(r, 250));
    const s = await chrome.tabs.sendMessage(tab.id, { type: 'amira:getStats' }, { frameId: 0 });
    if (s.total > 0 && s.pending === 0) return s;
  }
  return chrome.tabs.sendMessage(tab.id, { type: 'amira:getStats' }, { frameId: 0 });
}, URL_TEST);

const ms = Date.now() - t0;
const prefixed = await page.evaluate(() => (document.body.innerText.match(/⟦FF⟧/g) ?? []).length);
await page.screenshot({ path: 'tests/e2e/results/safinum.png', fullPage: true });

const report = { url: URL_TEST, ms, stats, prefixedSegmentsInPage: prefixed };
writeFileSync('tests/e2e/results/safinum.json', JSON.stringify(report, null, 2));
console.log(report);
await ctx.close();
if (stats.error) process.exit(1);
