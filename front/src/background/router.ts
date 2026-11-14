/**
 * Routeur de l'arrière-plan : choisit le client (vrai serveur ou mock), gère le cache des
 * traductions (textes MASQUÉS uniquement) et écrit le journal. Réutilisé tel quel par le faux
 * chrome.* du mode `npm run dev`.
 */
import { AmiraApi, ApiError, HttpApi, TranslateResponse, TranslateSegmentOut } from '../services/api';
import { EmbeddedApi } from '../services/embedded';
import { MockApi } from '../services/mock';
import { appendLog } from '../services/log';
import { loadSettings, Settings } from '../services/settings';
import { API_URL, EMBEDDED, USE_MOCK } from '../config';
import type { BgRequest, BgResult, StatusResult } from '../shared/messages';

const CACHE_KEY = 'amira.cache';
const CACHE_MAX = 1000;

let mock: MockApi | null = null;
let embedded: EmbeddedApi | null = null;
let statusCache: { at: number; key: string; value: StatusResult } | null = null;

/** Back-end Amira fixé à la construction ; simulation tant qu'aucune adresse n'est fournie. */
function apiFor(s: Settings): AmiraApi | null {
  if (EMBEDDED) return (embedded ??= new EmbeddedApi(API_URL ? new HttpApi(API_URL) : null));
  if (USE_MOCK) {
    mock ??= new MockApi();
    mock.scenario = s.mockScenario;
    return mock;
  }
  return new HttpApi(API_URL);
}

function errResult(e: unknown): BgResult<never> {
  if (e instanceof ApiError) return { ok: false, code: e.code, message: e.message, retryAfterMs: e.retryAfterMs };
  return { ok: false, code: 'CLIENT_ERROR', message: 'Erreur interne de l’extension' };
}

function logServerError(e: unknown, requestId?: string, hote?: string) {
  if (e instanceof ApiError) {
    void appendLog({
      niveau: 'error',
      source: e.code === 'NOT_CONFIGURED' ? 'extension' : 'serveur',
      code: e.code,
      message: e.message,
      httpStatus: e.httpStatus,
      durationMs: e.durationMs,
      requestId,
      hote,
    });
  } else {
    void appendLog({ niveau: 'error', source: 'extension', code: 'CLIENT_ERROR', message: (e as Error)?.name ?? 'Erreur', requestId, hote });
  }
}

type CacheMap = Record<string, TranslateSegmentOut & { at: number }>;

async function readCache(): Promise<CacheMap> {
  const got = await chrome.storage.local.get(CACHE_KEY);
  return (got[CACHE_KEY] as CacheMap) ?? {};
}

function cacheKey(req: { source: string; target: string; variety: string | null }, text: string) {
  return `${req.source}>${req.target}|${req.variety}|${text}`;
}

export async function getStatus(force = false): Promise<StatusResult> {
  const s = await loadSettings();
  const key = `${USE_MOCK}|${EMBEDDED}|${s.mockScenario}`;
  if (!force && statusCache && statusCache.key === key && Date.now() - statusCache.at < 20_000) return statusCache.value;
  const api = apiFor(s);
  let value: StatusResult;
  if (!api) value = { state: 'notConnected', demo: false, capabilities: null };
  else {
    try {
      await api.health();
      value = { state: 'ready', demo: USE_MOCK, autonomous: EMBEDDED, capabilities: await api.capabilities() };
    } catch (e) {
      const code = e instanceof ApiError ? e.code : 'CLIENT_ERROR';
      value = { state: code === 'NETWORK' || code === 'TIMEOUT' ? 'offline' : 'error', demo: USE_MOCK, capabilities: null, errorCode: code };
      logServerError(e);
    }
  }
  statusCache = { at: Date.now(), key, value };
  return value;
}

export async function handle(msg: BgRequest): Promise<unknown> {
  switch (msg.type) {
    case 'amira:status':
      return getStatus(true);

    case 'amira:translate': {
      const s = await loadSettings();
      const api = apiFor(s);
      const { req, hote } = msg;
      if (!api) {
        void appendLog({ niveau: 'warn', source: 'extension', code: 'NOT_CONFIGURED', message: 'Traduction demandée sans serveur', hote, requestId: req.requestId });
        return { ok: false, code: 'NOT_CONFIGURED', message: 'Serveur non connecté' };
      }
      const cache = await readCache();
      const hits: TranslateSegmentOut[] = [];
      const missing = req.segments.filter((seg) => {
        const c = cache[cacheKey(req, seg.text)];
        if (c) hits.push({ ...c, id: seg.id });
        return !c;
      });
      const t0 = performance.now();
      try {
        let res: TranslateResponse = { requestId: req.requestId, engineVersion: 'cache', latencyMs: 0, segments: [] };
        if (missing.length) res = await api.translate({ ...req, segments: missing });
        const durationMs = Math.round(performance.now() - t0);
        // n'entre en cache que ce qui est fiable ; les textes sont masqués
        const byId = new Map(missing.map((m) => [m.id, m.text]));
        for (const out of res.segments) {
          const src = byId.get(out.id);
          if (src && out.status !== 'uncertain') cache[cacheKey(req, src)] = { ...out, at: Date.now() };
        }
        const keys = Object.keys(cache);
        if (keys.length > CACHE_MAX) {
          keys.sort((a, b) => cache[a].at - cache[b].at).slice(0, keys.length - CACHE_MAX).forEach((k) => delete cache[k]);
        }
        await chrome.storage.local.set({ [CACHE_KEY]: cache });
        void appendLog({
          niveau: 'info',
          source: 'serveur',
          code: 'TRANSLATE_OK',
          message: `${req.segments.length} segments, ${hits.length} depuis le cache`,
          durationMs,
          requestId: req.requestId,
          hote,
        });
        return { ok: true, data: { ...res, segments: [...hits, ...res.segments], fromCache: hits.length } };
      } catch (e) {
        logServerError(e, req.requestId, hote);
        return errResult(e);
      }
    }

    case 'amira:tts': {
      const s = await loadSettings();
      const api = apiFor(s);
      if (!api) return { ok: false, code: 'NOT_CONFIGURED', message: 'Serveur non connecté' };
      try {
        return { ok: true, data: await api.tts(msg.req) };
      } catch (e) {
        logServerError(e);
        return errResult(e);
      }
    }

    case 'amira:stt': {
      const s = await loadSettings();
      const api = apiFor(s);
      if (!api) return { ok: false, code: 'NOT_CONFIGURED', message: 'Serveur non connecté' };
      try {
        return { ok: true, data: await api.stt(msg.audioBase64, msg.mimeType, msg.language) };
      } catch (e) {
        logServerError(e);
        return errResult(e);
      }
    }

    case 'amira:feedback': {
      const s = await loadSettings();
      const api = apiFor(s);
      if (!api) return { ok: false, code: 'NOT_CONFIGURED', message: 'Serveur non connecté' };
      try {
        await api.feedback(msg.req);
        void appendLog({ niveau: 'info', source: 'client', code: 'FEEDBACK_SENT', message: 'Signalement envoyé' });
        return { ok: true, data: null };
      } catch (e) {
        logServerError(e);
        return errResult(e);
      }
    }

    case 'amira:log':
      await appendLog(msg.entry);
      return { ok: true, data: null };

    case 'amira:clearCache':
      await chrome.storage.local.remove(CACHE_KEY);
      void appendLog({ niveau: 'info', source: 'extension', code: 'CACHE_CLEARED', message: 'Cache vidé' });
      return { ok: true, data: null };
  }
}
