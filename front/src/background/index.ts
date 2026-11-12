/// <reference types="chrome" />
import { handle } from './router';
import { appendLog } from '../services/log';
import { loadSettings } from '../services/settings';
import type { BgRequest } from '../shared/messages';

const DYNAMIC_SCRIPT_ID = 'amira-sites';

chrome.sidePanel?.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => undefined);

chrome.runtime.onMessage.addListener((msg: BgRequest, _sender, sendResponse) => {
  if (!msg || typeof msg.type !== 'string' || !msg.type.startsWith('amira:')) return false;
  if (!['amira:translate', 'amira:status', 'amira:tts', 'amira:stt', 'amira:feedback', 'amira:log', 'amira:clearCache'].includes(msg.type)) return false;
  handle(msg)
    .then(sendResponse)
    .catch((e) => {
      void appendLog({ niveau: 'error', source: 'extension', code: 'BG_HANDLER', message: (e as Error)?.name ?? 'Erreur' });
      sendResponse({ ok: false, code: 'CLIENT_ERROR', message: 'Erreur interne de l’extension' });
    });
  return true;
});

/** Sites ajoutés à la demande : on enregistre le script de contenu pour les origines autorisées. */
async function syncDynamicScripts() {
  const s = await loadSettings();
  const ALL = ['https://*/*', 'http://*/*'];
  const granted: string[] = [];
  if (s.allSites && (await chrome.permissions.contains({ origins: ALL }))) {
    granted.push(...ALL);
  } else {
    for (const pattern of s.enabledSites.filter((p) => p !== 'https://safinum.cm/*')) {
      if (await chrome.permissions.contains({ origins: [pattern] })) granted.push(pattern);
    }
  }
  try {
    await chrome.scripting.unregisterContentScripts({ ids: [DYNAMIC_SCRIPT_ID] });
  } catch {
    /* rien à retirer */
  }
  if (granted.length) {
    await chrome.scripting.registerContentScripts([
      { id: DYNAMIC_SCRIPT_ID, matches: granted, excludeMatches: ['https://safinum.cm/*'], js: ['content.js'], allFrames: true, runAt: 'document_idle', persistAcrossSessions: true },
    ]);
  }
}

chrome.runtime.onInstalled.addListener(() => {
  void syncDynamicScripts();
  // nouvelle version ou extension rechargée : les traductions gardées peuvent dater d'un ancien gold ou du mode démo
  void chrome.storage.local.remove('amira.cache');
  void appendLog({ niveau: 'info', source: 'extension', code: 'INSTALLED', message: 'Extension installée ou mise à jour' });
});
chrome.permissions.onAdded.addListener(() => void syncDynamicScripts());
chrome.permissions.onRemoved.addListener(() => void syncDynamicScripts());
chrome.storage.onChanged.addListener((changes) => {
  if (changes['amira.settings']) void syncDynamicScripts();
});

chrome.commands?.onCommand.addListener(async (command) => {
  if (command !== 'toggle-translation') return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return;
  try {
    const stats = await chrome.tabs.sendMessage(tab.id, { type: 'amira:getStats' });
    await chrome.tabs.sendMessage(tab.id, { type: 'amira:setEnabled', enabled: !stats?.enabled });
  } catch {
    void appendLog({ niveau: 'warn', source: 'extension', code: 'NO_CONTENT_SCRIPT', message: 'Page non activée pour Amira', hote: tab.url });
  }
});
