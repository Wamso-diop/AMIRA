/**
 * Script de contenu : relie le moteur à chrome.*.
 * SÉCURITÉ : ne lit ni balises meta, ni cookies, ni valeurs de champs ; ne clique, ne remplit et
 * ne soumet rien. Seuls des textes MASQUÉS partent vers l'arrière-plan.
 */
import { Engine, type EngineSettings } from './engine';
import { Picker } from './picker';
import { normalizeSettings, SETTINGS_KEY, type Settings } from '../services/settings';
import type { BgRequest, ContentCommand, ContentEvent, TranslateResult } from '../shared/messages';
import type { LogEntry } from '../services/log';

declare global {
  interface Window {
    __amiraContent?: boolean;
  }
}

const ACTIVE_HOSTS_KEY = 'amira.activeHosts';

function toEngineSettings(s: Settings): EngineSettings {
  return {
    ffTarget: s.ffTarget,
    variety: s.variety,
    display: s.display,
    prudence: s.prudence,
    confidenceThreshold: s.confidenceThreshold,
    extraNames: s.extraNames,
  };
}

function send<T>(msg: BgRequest | ContentEvent): Promise<T> {
  return chrome.runtime.sendMessage(msg) as Promise<T>;
}

function log(entry: Partial<LogEntry>) {
  void send({ type: 'amira:log', entry: { ...entry, hote: location.hostname } }).catch(() => undefined);
}

async function main() {
  if (window.__amiraContent) return;
  window.__amiraContent = true;

  const got = await chrome.storage.local.get([SETTINGS_KEY, ACTIVE_HOSTS_KEY]);
  let settings = normalizeSettings(got[SETTINGS_KEY]);
  const isTop = window === window.top;

  const engine = new Engine({
    doc: document,
    settings: toEngineSettings(settings),
    translate: (req) => send<TranslateResult>({ type: 'amira:translate', req, hote: location.hostname }),
    log,
    onStats: (stats) => void send({ type: 'amira:stats', stats }).catch(() => undefined),
    onWarning: (text) => void send({ type: 'amira:warning', text }).catch(() => undefined),
  });

  const picker = new Picker(
    document,
    () => engine.pickables(),
    (state) => void send({ type: 'amira:picked', state }).catch(() => undefined),
    () => settings.uiLanguage,
  );

  const setEnabled = async (on: boolean) => {
    if (on) engine.enable();
    else engine.disable();
    // le choix est mémorisé par hôte pour suivre un parcours sur plusieurs pages
    if (isTop) {
      const cur = ((await chrome.storage.local.get(ACTIVE_HOSTS_KEY))[ACTIVE_HOSTS_KEY] as Record<string, boolean>) ?? {};
      if (on) cur[location.hostname] = true;
      else delete cur[location.hostname];
      await chrome.storage.local.set({ [ACTIVE_HOSTS_KEY]: cur });
    }
  };

  const activeHosts = (got[ACTIVE_HOSTS_KEY] as Record<string, boolean>) ?? {};
  let topHost = location.hostname;
  try {
    topHost = window.top!.location.hostname;
  } catch {
    /* iframe d'une autre origine : on suit l'hôte de la frame */
  }
  if (activeHosts[topHost] || activeHosts[location.hostname]) engine.enable();

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'local') return;
    if (changes[SETTINGS_KEY]) {
      settings = normalizeSettings(changes[SETTINGS_KEY].newValue);
      engine.updateSettings(toEngineSettings(settings));
    }
    if (changes[ACTIVE_HOSTS_KEY] && !isTop) {
      const hosts = (changes[ACTIVE_HOSTS_KEY].newValue as Record<string, boolean>) ?? {};
      const on = !!(hosts[topHost] || hosts[location.hostname]);
      if (on !== engine.enabled) {
        if (on) engine.enable();
        else engine.disable();
      }
    }
  });

  chrome.runtime.onMessage.addListener((msg: ContentCommand, _sender, sendResponse) => {
    if (!msg || typeof msg.type !== 'string') return false;
    switch (msg.type) {
      case 'amira:setEnabled':
        void setEnabled(msg.enabled).then(() => sendResponse(engine.stats()));
        return true;
      case 'amira:showOriginal':
        engine.setShowOriginal(msg.on);
        sendResponse(engine.stats());
        return false;
      case 'amira:getStats':
        sendResponse(engine.stats());
        void send({ type: 'amira:stats', stats: engine.stats() }).catch(() => undefined);
        return false;
      case 'amira:retry':
        engine.retry();
        sendResponse(engine.stats());
        return false;
      case 'amira:readable':
        sendResponse(engine.readable(msg.what));
        return false;
      case 'amira:pick':
        if (!isTop) return false;
        sendResponse(picker.handle(msg));
        return false;
    }
    return false;
  });

  window.addEventListener('error', (ev) => {
    // erreurs de l'extension seulement (fichier content.js), sans message de la page
    if (typeof ev.filename === 'string' && ev.filename.startsWith('chrome-extension://')) {
      log({ niveau: 'error', source: 'extension', code: 'CONTENT_ERROR', message: ev.error?.name ?? 'Erreur' });
    }
  });
}

main().catch(() => {
  log({ niveau: 'error', source: 'extension', code: 'CONTENT_INIT_FAILED', message: 'Démarrage du script de contenu impossible' });
});
