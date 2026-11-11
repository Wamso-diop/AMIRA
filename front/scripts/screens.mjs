// Captures du panneau à 320, 400 et 480 px (mode développement, faux chrome.*).
// Usage : npm run screens   → docs/captures/*.png
import { chromium } from '@playwright/test';
import { spawn } from 'node:child_process';
import { mkdirSync } from 'node:fs';

const PORT = 5199;
const OUT = 'docs/captures';
mkdirSync(OUT, { recursive: true });

const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--port', String(PORT), '--strictPort'], { stdio: 'pipe', env: { ...process.env, BROWSER: 'none' } });
// le serveur s'arrête toujours avec le script, même en cas d'erreur
process.on('exit', () => server.kill());
process.on('uncaughtException', (e) => { console.error(e); process.exit(1); });
process.on('unhandledRejection', (e) => { console.error(e); process.exit(1); });
await new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error('Vite ne démarre pas')), 30000);
  server.stdout.on('data', (d) => String(d).includes('Local') && (clearTimeout(timer), resolve()));
});

const executablePath = process.env.CHROME_PATH || undefined;
const browser = await chromium.launch({ executablePath });
const base = `http://localhost:${PORT}/sidepanel.html`;

async function shot(width, name, { settings = {}, theme = 'light', action } = {}) {
  const ctx = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: theme, reducedMotion: 'reduce', deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.addInitScript((s) => {
    if (!s) return;
    localStorage.setItem('amira-dev:amira.settings', JSON.stringify({ onboarded: true, ...s }));
  }, settings);
  await page.goto(base);
  await page.waitForSelector('.app, .onb');
  if (action) await action(page);
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/${name}-${width}.png`, fullPage: true });
  await ctx.close();
}

const enableAndTranslate = async (page) => {
  await page.getByRole('switch', { name: /Traduire cette page/ }).check({ force: true });
  await page.waitForTimeout(900);
};

for (const w of [320, 400, 480]) {
  await shot(w, 'accueil', { settings: { onboarded: false } });
  await shot(w, 'traduire', { settings: {}, action: enableAndTranslate });
  await shot(w, 'traduire-sombre', { settings: { theme: 'dark' }, theme: 'dark', action: enableAndTranslate });
  await shot(w, 'erreur', { settings: { mockScenario: 'http500' } });
  await shot(w, 'voix', { settings: {}, action: (p) => p.getByRole('tab', { name: 'Voix' }).click() });
  await shot(w, 'reglages', { settings: {}, action: (p) => p.getByRole('tab', { name: 'Réglages' }).click() });
  await shot(w, 'journal', {
    settings: {},
    action: async (p) => {
      await enableAndTranslate(p);
      await p.getByRole('tab', { name: 'Journal' }).click();
    },
  });
}

await browser.close();
server.kill();
console.log(`Captures enregistrées dans ${OUT}/`);
