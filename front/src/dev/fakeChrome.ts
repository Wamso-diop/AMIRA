/**
 * Faux chrome.* pour voir le panneau dans un onglet normal (`npm run dev`), sans installer l'extension.
 * - storage.local : localStorage
 * - runtime.sendMessage : le VRAI routeur de l'arrière-plan (mock ou serveur réel)
 * - tabs.sendMessage : un VRAI moteur de contenu sur une page de démonstration en mémoire
 */
import { handle } from '../background/router';
import { Engine } from '../content/engine';
import { Picker } from '../content/picker';
import { normalizeSettings, SETTINGS_KEY } from '../services/settings';
import type { BgRequest, ContentCommand, ContentEvent, TranslateResult } from '../shared/messages';

type Listener = (...args: any[]) => unknown; // eslint-disable-line @typescript-eslint/no-explicit-any

const DEMO_PAGE = `<!doctype html><html lang="fr"><body>
<header><h1>Mon compte</h1><nav><a href="#">Accueil</a> <a href="#">Transferts</a></nav></header>
<main>
  <section><h2>Solde disponible</h2><p>Votre solde est de <strong>125 000 FCFA</strong> au 12/03/2025.</p></section>
  <section><h2>Frais</h2><p>Des frais de 1 % s’appliquent à chaque transfert, avec un minimum de 100 FCFA.</p></section>
  <form><label>Numéro du bénéficiaire <input name="tel" placeholder="Ex. : 6XX XX XX XX"></label>
    <p>Bénéficiaire : Jean Mbarga</p><button type="button">Continuer</button></form>
  <div role="alert" class="alert-warning">Ne communiquez jamais votre code secret, même à un agent.</div>
  <p class="error">Solde insuffisant pour effectuer ce transfert.</p>
</main></body></html>`;

function event() {
  const listeners = new Set<Listener>();
  return {
    addListener: (l: Listener) => listeners.add(l),
    removeListener: (l: Listener) => listeners.delete(l),
    hasListener: (l: Listener) => listeners.has(l),
    emit: (...args: unknown[]) => [...listeners].map((l) => l(...args)),
  };
}

export function installFakeChrome(): void {
  const PREFIX = 'amira-dev:';
  const storageChanged = event();
  const runtimeMessage = event();
  const read = (k: string) => {
    const v = localStorage.getItem(PREFIX + k);
    return v === null ? undefined : JSON.parse(v);
  };

  const local = {
    async get(keys?: string | string[] | null) {
      const list = keys == null ? Object.keys(localStorage).filter((k) => k.startsWith(PREFIX)).map((k) => k.slice(PREFIX.length)) : Array.isArray(keys) ? keys : [keys];
      const out: Record<string, unknown> = {};
      for (const k of list) {
        const v = read(k);
        if (v !== undefined) out[k] = v;
      }
      return out;
    },
    async set(items: Record<string, unknown>) {
      const changes: Record<string, chrome.storage.StorageChange> = {};
      for (const [k, v] of Object.entries(items)) {
        changes[k] = { oldValue: read(k), newValue: v };
        localStorage.setItem(PREFIX + k, JSON.stringify(v));
      }
      storageChanged.emit(changes, 'local');
    },
    async remove(keys: string | string[]) {
      const changes: Record<string, chrome.storage.StorageChange> = {};
      for (const k of Array.isArray(keys) ? keys : [keys]) {
        changes[k] = { oldValue: read(k) };
        localStorage.removeItem(PREFIX + k);
      }
      storageChanged.emit(changes, 'local');
    },
  };

  // Moteur de contenu : sur la page visible de l'aperçu (apercu.html, cadre de gauche) si elle existe,
  // sinon sur une page de démonstration en mémoire.
  const siteFrame = (): HTMLIFrameElement | null => {
    try {
      return window.parent !== window ? (window.parent.document.getElementById('amira-site') as HTMLIFrameElement | null) : null;
    } catch {
      return null;
    }
  };
  const sendRuntime = (msg: BgRequest | ContentEvent): Promise<unknown> => {
    if (msg.type === 'amira:stats' || msg.type === 'amira:error' || msg.type === 'amira:picked') {
      runtimeMessage.emit(msg, { tab: { id: 1 }, frameId: 0 }, () => undefined);
      return Promise.resolve();
    }
    return handle(msg as BgRequest);
  };
  const toEngine = (n: ReturnType<typeof normalizeSettings>) => ({
    returnLang: n.returnLang, variety: n.variety, display: n.display,
    prudence: n.prudence, confidenceThreshold: n.confidenceThreshold, extraNames: n.extraNames,
  });
  let engine: Engine | null = null;
  let wasEnabled = false;
  const pageDoc = async (): Promise<Document> => {
    const frame = siteFrame();
    if (!frame) return new DOMParser().parseFromString(DEMO_PAGE, 'text/html');
    if (frame.contentDocument?.readyState !== 'complete') await new Promise((r) => frame.addEventListener('load', r, { once: true }));
    return frame.contentDocument!;
  };
  const getEngine = async () => {
    if (engine) return engine;
    const s = normalizeSettings((await local.get(SETTINGS_KEY))[SETTINGS_KEY]);
    const doc = await pageDoc();
    engine = new Engine({
      doc,
      settings: toEngine(s),
      translate: (req) => handle({ type: 'amira:translate', req, hote: 'safinum.cm' }) as Promise<TranslateResult>,
      log: (entry) => void handle({ type: 'amira:log', entry: { ...entry, hote: 'safinum.cm' } }),
      onStats: (stats) => void sendRuntime({ type: 'amira:stats', stats: { ...stats, hote: 'safinum.cm' } }),
    });
    return engine;
  };
  storageChanged.addListener((changes: Record<string, chrome.storage.StorageChange>) => {
    if (changes[SETTINGS_KEY] && engine) engine.updateSettings(toEngine(normalizeSettings(changes[SETTINGS_KEY].newValue)));
  });
  // La page de gauche se recharge : comme dans Chrome, Amira reprend sur la nouvelle page si elle était active.
  siteFrame()?.addEventListener('load', async () => {
    wasEnabled = !!engine?.enabled;
    engine = null;
    const e = await getEngine();
    if (wasEnabled) e.enable();
    void sendRuntime({ type: 'amira:stats', stats: { ...e.stats(), hote: 'safinum.cm' } });
  });

  let picker: { engine: Engine; p: Picker } | null = null;
  const getPicker = (e: Engine) => {
    if (picker?.engine !== e) {
      picker = {
        engine: e,
        p: new Picker(e.deps.doc, () => e.pickables(), (state) => void sendRuntime({ type: 'amira:picked', state }), () => 'fr'),
      };
    }
    return picker.p;
  };

  const tab = { id: 1, windowId: 1, active: true, url: 'https://safinum.cm/hackathon-test', title: 'SAFINUM — test' };

  const fake = {
    runtime: {
      id: 'amira-dev',
      sendMessage: sendRuntime,
      onMessage: runtimeMessage,
      getURL: (p: string) => p,
    },
    storage: { local, onChanged: storageChanged },
    tabs: {
      query: async () => [tab],
      onActivated: event(),
      onUpdated: event(),
      create: async ({ url }: { url: string }) => {
        window.open(url, '_blank', 'noopener');
      },
      sendMessage: async (_id: number, cmd: ContentCommand) => {
        const e = await getEngine();
        switch (cmd.type) {
          case 'amira:setEnabled':
            if (cmd.enabled) e.enable();
            else e.disable();
            return { ...e.stats(), hote: 'safinum.cm' };
          case 'amira:showOriginal':
            e.setShowOriginal(cmd.on);
            return { ...e.stats(), hote: 'safinum.cm' };
          case 'amira:retry':
            e.retry();
            return { ...e.stats(), hote: 'safinum.cm' };
          case 'amira:readable':
            return e.readable(cmd.what);
          case 'amira:pick':
            return getPicker(e).handle(cmd);
          default:
            return { ...e.stats(), hote: 'safinum.cm' };
        }
      },
    },
    permissions: {
      request: async () => true,
      contains: async () => true,
      onAdded: event(),
      onRemoved: event(),
    },
  };
  (globalThis as unknown as { chrome: unknown }).chrome = fake;
  console.info('[Amira] Mode développement : faux chrome.* installé (page de démonstration en mémoire).');
}
