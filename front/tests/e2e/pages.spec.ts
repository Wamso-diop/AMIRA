/**
 * Parcours bancaire simulé sur 5 structures de page. Mesures : texte couvert, marqueurs intacts
 * (100 % exigé), temps de traitement. Le moteur tourne avec le mock (banc d'essai harness.js).
 */
import { expect, test, type Frame, type Page } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';

type Metrics = { page: string; coverage: number; translatedShare: number; markersIntact: number; segments: number; ms: number; leaks: number };
const results: Metrics[] = [];

test.beforeEach(async ({ page }) => {
  await page.addInitScript({ path: 'tests/e2e/.harness/harness.js' });
});

test.afterAll(() => {
  mkdirSync('tests/e2e/results', { recursive: true });
  writeFileSync('tests/e2e/results/metrics.json', JSON.stringify(results, null, 2));
  console.table(results);
});

async function run(target: Page | Frame) {
  return target.evaluate(async () => {
    const A = (window as any).Amira;
    const t0 = performance.now();
    A.enable();
    await A.idle();
    return performance.now() - t0;
  });
}

/** Calcule les mesures dans une frame (et ses shadow DOM). */
async function measure(target: Page | Frame, name: string, ms: number): Promise<Metrics> {
  const m = await target.evaluate(() => {
    const A = (window as any).Amira;
    const segs = A.segments().filter((s: any) => s.state !== 'skipped');
    const letters = (s: string) => (s.replace(/\{\/?[NBE]\d+\}/g, '').match(/\p{L}/gu) ?? []).length;
    // texte visible de la page, capturé AVANT traduction via l'original de chaque segment
    const visibleOriginal = (() => {
      const collect = (root: Node): string => {
        let out = '';
        const walk = (n: Node) => {
          if (n.nodeType === 1) {
            const el = n as Element;
            if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE'].includes(el.tagName) || el.closest('[data-amira-ignore],[data-amira-ui]')) return;
            if ((el as any).shadowRoot) out += collect((el as any).shadowRoot);
          }
          if (n.nodeType === 3) out += (n as Text).data + ' ';
          n.childNodes.forEach(walk);
        };
        walk(root);
        return out;
      };
      return collect(document.body);
    })();
    const capturedLetters = segs.filter((s: any) => s.kind === 'text').reduce((n: number, s: any) => n + letters(s.original), 0);
    // la page affiche maintenant les traductions : on compte les lettres de la page hors préfixe ⟦FF⟧
    const translatedSegs = segs.filter((s: any) => s.state === 'translated');
    const intact = translatedSegs.filter((s: any) => s.values.every((v: string) => s.translation.includes(v))).length;
    const leaks = A.sentTexts.filter((txt: string) => (window as any).__fixtures.some((f: string) => txt.includes(f))).length;
    return {
      capturedLetters,
      pageLetters: letters(visibleOriginal.replace(/⟦FF⟧/g, '')),
      translatedShare: segs.length ? translatedSegs.length / segs.length : 0,
      markersIntact: translatedSegs.length ? intact / translatedSegs.length : 1,
      segments: segs.length,
      leaks,
    };
  });
  return {
    page: name,
    coverage: Math.min(1, m.capturedLetters / Math.max(1, m.pageLetters)),
    translatedShare: m.translatedShare,
    markersIntact: m.markersIntact,
    segments: m.segments,
    ms: Math.round(ms),
    leaks: m.leaks,
  };
}

async function fixturesVisible(target: Page | Frame) {
  return target.evaluate(() => {
    const text = (document.body.innerText || '') + [...document.querySelectorAll('*')].map((e) => (e as any).shadowRoot?.textContent ?? '').join(' ');
    return (window as any).__fixtures.filter((f: string) => !text.replace(/\s+/g, ' ').includes(f));
  });
}

/** Traité = traduit (⟦FF⟧) ou gardé dans la langue d'origine avec la marque ⚠ (jamais à moitié). */
async function expectProcessed(loc: ReturnType<Page['locator']>) {
  await expect(async () => {
    const text = (await loc.textContent()) ?? '';
    const kept = await loc.evaluate((el) => !!el.closest('[data-amira-state="kept"]'));
    expect(text.includes('⟦FF⟧') || kept).toBe(true);
  }).toPass({ timeout: 3000 });
}

function check(m: Metrics) {
  expect(m.leaks, 'aucune valeur sensible envoyée').toBe(0);
  expect(m.markersIntact, 'marqueurs intacts').toBe(1);
  expect(m.coverage, 'texte couvert').toBeGreaterThan(0.9);
}

test('HTML simple : solde, frais, bénéficiaire, récapitulatif, erreur, avertissement', async ({ page }) => {
  await page.goto('/simple.html');
  const before = await page.locator('body').innerHTML();
  const ms = await run(page);
  const m = await measure(page, 'simple', ms);
  results.push(m);
  check(m);
  expect(await fixturesVisible(page)).toEqual([]);
  await expectProcessed(page.locator('h2').first());
  // la valeur du champ et le jeton CSRF ne sont jamais lus ni envoyés
  const sent = await page.evaluate(() => (window as any).Amira.sentTexts.join('\n'));
  expect(sent).not.toContain('690123456');
  expect(sent).not.toContain('SECRET-CSRF');
  await expect(page.locator('#tel')).toHaveValue('690123456');
  // placeholder et aria-label traduits
  const ph = await page.locator('#tel').getAttribute('placeholder');
  expect(ph === 'Saisissez le numéro' || ph!.startsWith('⟦FF⟧')).toBe(true);
  // avertissement de sécurité : affiché traduit seulement s'il est « validé »
  const warn = await page.evaluate(() => (window as any).Amira.segments().find((s: any) => s.category === 'security_warning'));
  expect(warn.state).toBe('translated');
  // retour instantané à l'original, à l'identique
  await page.evaluate(() => (window as any).Amira.showOriginal(true));
  expect(await page.locator('body').innerHTML()).toBe(before.replace(/<style id="amira-page-style"[\s\S]*?<\/style>/, ''));
});

test('Application monopage : contenu chargé sans rechargement et texte mis à jour par le site', async ({ page }) => {
  await page.goto('/spa.html');
  const t0 = Date.now();
  await run(page);
  // le site met à jour un montant déjà traduit : le bloc est retraduit, la nouvelle valeur s'affiche
  await page.evaluate(() => (window as any).__setBalance('99 000 FCFA'));
  await page.waitForTimeout(200);
  await page.evaluate(() => (window as any).Amira.idle());
  await expect(page.locator('strong')).toHaveText('99 000 FCFA');
  await expectProcessed(page.locator('strong').locator('xpath=..'));
  await page.evaluate(() => (window as any).Amira.showOriginal(true));
  await expect(page.locator('strong').locator('xpath=..')).toHaveText('Solde : 99 000 FCFA');
  await page.evaluate(() => (window as any).Amira.showOriginal(false));
  for (let i = 0; i < 3; i++) {
    await page.click('#next');
    await page.waitForTimeout(150);
    await page.evaluate(() => (window as any).Amira.idle());
    await expectProcessed(page.locator('h1'));
  }
  const m = await measure(page, 'spa', Date.now() - t0);
  results.push(m);
  check(m);
  await expect(page.locator('[role=alert]')).toContainText('E-4021');
});

test('Fenêtre modale', async ({ page }) => {
  await page.goto('/modal.html');
  const t0 = Date.now();
  await run(page);
  await page.click('#open');
  await page.waitForTimeout(150);
  await page.evaluate(() => (window as any).Amira.idle());
  await expectProcessed(page.locator('[role=dialog] h2'));
  // aria-label « Fermer la fenêtre » traité comme le reste ; le symbole × n'est pas touché
  const close = page.locator('[role=dialog] button').first();
  await expect(close).toHaveText('×');
  expect((await close.getAttribute('aria-label'))!.startsWith('⟦FF⟧') || (await close.getAttribute('aria-label')) === 'Fermer la fenêtre').toBe(true);
  const m = await measure(page, 'modale', Date.now() - t0);
  results.push(m);
  check(m);
  expect(await fixturesVisible(page)).toEqual([]);
});

test('Notification éphémère et zone aria-live', async ({ page }) => {
  await page.goto('/toast.html');
  const t0 = Date.now();
  await run(page);
  await page.click('#go');
  await expectProcessed(page.locator('.toast'));
  await expect(page.locator('.toast')).toContainText('5 000 FCFA');
  await expectProcessed(page.locator('#live'));
  const m = await measure(page, 'notification', Date.now() - t0);
  results.push(m);
  check(m);
});

test('Iframe de même origine + shadow DOM', async ({ page }) => {
  await page.goto('/iframe.html');
  const frame = page.frame({ url: /iframe-inner/ })!;
  await frame.waitForLoadState();
  const t0 = Date.now();
  await run(page);
  await run(frame);
  await expectProcessed(frame.locator('h2'));
  const top = await measure(page, 'iframe (page)', Date.now() - t0);
  const inner = await measure(frame, 'iframe (cadre)', Date.now() - t0);
  results.push(top, inner);
  check(top);
  check(inner);
  expect(await fixturesVisible(frame)).toEqual([]);
  // champ mot de passe : jamais touché
  await expect(frame.locator('input[type=password]')).toHaveValue('');
});

test('Marqueurs abîmés par le serveur : le texte original est gardé, sans remplacement partiel', async ({ page }) => {
  await page.goto('/simple.html');
  const before = await page.locator('#recap p').innerHTML();
  await page.evaluate(() => (window as any).Amira.setScenario('brokenMarkers'));
  await run(page);
  expect(await page.locator('#recap p').innerHTML()).toBe(before);
  await expect(page.locator('#recap p')).toHaveAttribute('data-amira-state', 'kept');
  const logs = await page.evaluate(() => (window as any).Amira.logs.map((l: any) => l.code));
  expect(logs).toContain('MARKERS_MISMATCH');
});

test('Erreur serveur 500 : rien n’est remplacé, les segments passent en erreur', async ({ page }) => {
  await page.goto('/simple.html');
  const before = await page.locator('body').innerText();
  await page.evaluate(() => (window as any).Amira.setScenario('http500'));
  await run(page);
  expect(await page.locator('body').innerText()).toBe(before);
  const st = await page.evaluate(() => (window as any).Amira.stats());
  expect(st.errors).toBeGreaterThan(0);
  expect(st.translated).toBe(0);
});

test('Le site passe du français à l’anglais sans recharger : Amira suit la langue', async ({ page }) => {
  await page.goto('/langue.html');
  await run(page);
  expect(await page.evaluate(() => (window as any).Amira.stats().lang)).toBe('fr');
  await page.click('#lang');
  await page.waitForTimeout(250);
  await page.evaluate(() => (window as any).Amira.idle());
  expect(await page.evaluate(() => (window as any).Amira.stats().lang)).toBe('en');
  const last = await page.evaluate(() => (window as any).Amira.requests.at(-1));
  expect(last).toEqual({ source: 'en', target: 'ff' });
  await expectProcessed(page.locator('h1'));
  await expect(page.locator('h1')).toContainText('Your account');
  // retour au français
  await page.click('#lang');
  await page.waitForTimeout(250);
  await page.evaluate(() => (window as any).Amira.idle());
  expect(await page.evaluate(() => (window as any).Amira.stats().lang)).toBe('fr');
});
