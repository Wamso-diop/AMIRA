/**
 * Accès à la page de l'onglet actif, sur n'importe quel site web.
 * 1. Script déjà présent (safinum.cm, ou site déjà autorisé) : rien à faire.
 * 2. Accès temporaire donné par le clic sur l'icône Amira (activeTab) : injection directe.
 * 3. Sinon, Chrome demande UNE fois l'autorisation pour tous les sites web, puis injection.
 * Amira ne lit une page que lorsque « Traduire cette page » est activé.
 */
import type { Settings } from '../services/settings';
import { activeTab } from './bridge';

export const ALL_SITES = ['https://*/*', 'http://*/*'];

async function ping(tabId: number): Promise<boolean> {
  try {
    await chrome.tabs.sendMessage(tabId, { type: 'amira:getStats' }, { frameId: 0 });
    return true;
  } catch {
    return false;
  }
}

async function inject(tabId: number): Promise<boolean> {
  if (!chrome.scripting) return false;
  try {
    await chrome.scripting.executeScript({ target: { tabId, allFrames: true }, files: ['content.js'] });
  } catch {
    return false;
  }
  for (let i = 0; i < 10; i++) {
    if (await ping(tabId)) return true;
    await new Promise((r) => setTimeout(r, 50));
  }
  return false;
}

export async function ensureContent(update: (p: Partial<Settings>) => Promise<void>): Promise<void> {
  const tab = await activeTab();
  if (!tab?.id) throw new Error('NO_TAB');
  if (tab.url && !/^https?:/i.test(tab.url)) throw new Error('RESTRICTED');
  if (await ping(tab.id)) return;
  if (await inject(tab.id)) return;
  const granted = await chrome.permissions.request({ origins: ALL_SITES });
  if (!granted) throw new Error('PERMISSION_DENIED');
  await update({ allSites: true });
  if (await inject(tab.id)) return;
  throw new Error('RESTRICTED');
}

export async function setAllSites(on: boolean, update: (p: Partial<Settings>) => Promise<void>): Promise<boolean> {
  if (on) {
    const granted = await chrome.permissions.request({ origins: ALL_SITES });
    if (!granted) return false;
  } else {
    await chrome.permissions.remove({ origins: ALL_SITES }).catch(() => false);
  }
  await update({ allSites: on });
  return true;
}
