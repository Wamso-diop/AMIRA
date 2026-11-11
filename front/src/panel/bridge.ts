/** Échanges du panneau avec l'arrière-plan et l'onglet actif. */
import type { BgRequest, ContentCommand, PageStats, Readable } from '../shared/messages';

export function bg<T>(msg: BgRequest): Promise<T> {
  return chrome.runtime.sendMessage(msg) as Promise<T>;
}

export async function activeTab(): Promise<chrome.tabs.Tab | undefined> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

export class NoContentError extends Error {
  constructor() {
    super('NO_CONTENT');
  }
}

/** Envoie une commande au script de contenu de l'onglet actif (cadre principal). */
export async function toTab<T = PageStats>(cmd: ContentCommand): Promise<T> {
  const tab = await activeTab();
  if (!tab?.id) throw new Error('NO_TAB');
  try {
    if (cmd.type === 'amira:setEnabled' || cmd.type === 'amira:showOriginal' || cmd.type === 'amira:retry') {
      // toutes les frames (iframes comprises) reçoivent la commande ; on renvoie la réponse du cadre principal
      void chrome.tabs.sendMessage(tab.id, cmd).catch(() => undefined);
    }
    return (await chrome.tabs.sendMessage(tab.id, cmd, { frameId: 0 })) as T;
  } catch {
    throw new NoContentError();
  }
}

export async function readable(what: 'page' | 'selection' | 'messages' | 'report'): Promise<Readable> {
  return toTab<Readable>({ type: 'amira:readable', what });
}

/** Origine (motif) du site de l'onglet actif, ex. https://exemple.cm/* */
export async function activeOriginPattern(): Promise<string | null> {
  const tab = await activeTab();
  if (!tab?.url) return null;
  try {
    const u = new URL(tab.url);
    if (!/^https?:$/.test(u.protocol)) return null;
    return `${u.protocol}//${u.hostname}/*`;
  } catch {
    return null;
  }
}
