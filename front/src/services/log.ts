/**
 * Journal technique. Schéma versionné, rotation, stockage chrome.storage.local.
 * INTERDIT : texte de la page, montants, noms, numéros. Seulement l'hôte et des codes techniques.
 */

export type LogLevel = 'info' | 'warn' | 'error';
export type LogSource = 'client' | 'serveur' | 'extension';

export interface LogEntry {
  id: string;
  ts: number;
  niveau: LogLevel;
  source: LogSource;
  code: string;
  message: string;
  httpStatus?: number;
  durationMs?: number;
  requestId?: string;
  hote?: string;
}

export const LOG_KEY = 'amira.log';
export const LOG_SCHEMA_VERSION = 1;
export const LOG_MAX = 500;

interface LogStore {
  schema: number;
  entries: LogEntry[];
}

/** Messages autorisés : seulement des gabarits fixes par code, jamais du contenu libre venant de la page. */
const SAFE_MESSAGE = /^[\p{L}\s.,:;'’()\-/0-9%«»]{0,160}$/u;

/** Supprime tout ce qui ressemble à une donnée personnelle, par précaution. */
export function scrubMessage(msg: string): string {
  let m = String(msg ?? '').slice(0, 160);
  m = m.replace(/[\w.+-]+@[\w-]+\.[\w.]+/g, '[e-mail]');
  m = m.replace(/\+?\d[\d\s.\-]{5,}\d/g, '[nombre]');
  m = m.replace(/\d{4,}/g, '[nombre]');
  return SAFE_MESSAGE.test(m) ? m : m.replace(/[^\p{L}\s.,:;'’()\-/0-9%[\]]/gu, '');
}

/** Ne garde que le nom d'hôte (pas de chemin, pas de paramètres qui pourraient contenir des identifiants). */
export function hostOnly(url?: string): string | undefined {
  if (!url) return undefined;
  try {
    return new URL(url).hostname;
  } catch {
    return /^[a-z0-9.-]+$/i.test(url) ? url : undefined;
  }
}

export function sanitizeEntry(e: Partial<LogEntry>): LogEntry {
  const out: LogEntry = {
    id: e.id ?? Math.random().toString(36).slice(2, 10),
    ts: typeof e.ts === 'number' ? e.ts : Date.now(),
    niveau: e.niveau === 'warn' || e.niveau === 'error' ? e.niveau : 'info',
    source: e.source === 'serveur' || e.source === 'extension' ? e.source : 'client',
    code: String(e.code ?? 'UNKNOWN').replace(/[^A-Z0-9_]/gi, '').slice(0, 40) || 'UNKNOWN',
    message: scrubMessage(e.message ?? ''),
  };
  if (typeof e.httpStatus === 'number') out.httpStatus = e.httpStatus;
  if (typeof e.durationMs === 'number') out.durationMs = Math.round(e.durationMs);
  if (e.requestId && /^[a-z0-9-]{1,64}$/i.test(e.requestId)) out.requestId = e.requestId;
  const host = hostOnly(e.hote);
  if (host) out.hote = host;
  return out;
}

let queue: Promise<void> = Promise.resolve();

export function appendLog(e: Partial<LogEntry>): Promise<void> {
  const entry = sanitizeEntry(e);
  // sérialise les écritures pour ne rien perdre
  queue = queue.then(async () => {
    const store = await readStore();
    store.entries.push(entry);
    if (store.entries.length > LOG_MAX) store.entries.splice(0, store.entries.length - LOG_MAX);
    await chrome.storage.local.set({ [LOG_KEY]: store });
  }).catch(() => undefined);
  return queue;
}

async function readStore(): Promise<LogStore> {
  const got = await chrome.storage.local.get(LOG_KEY);
  const raw = got[LOG_KEY] as LogStore | undefined;
  if (!raw || raw.schema !== LOG_SCHEMA_VERSION || !Array.isArray(raw.entries)) {
    // schéma inconnu ou ancien : on repart d'un journal vide plutôt que de mal interpréter
    return { schema: LOG_SCHEMA_VERSION, entries: [] };
  }
  return raw;
}

export async function readLog(): Promise<LogEntry[]> {
  return (await readStore()).entries;
}

export async function clearLog(): Promise<void> {
  await chrome.storage.local.set({ [LOG_KEY]: { schema: LOG_SCHEMA_VERSION, entries: [] } });
}

export function exportLog(entries: LogEntry[]): string {
  return JSON.stringify({ schema: LOG_SCHEMA_VERSION, exportedAt: new Date().toISOString(), entries }, null, 2);
}
