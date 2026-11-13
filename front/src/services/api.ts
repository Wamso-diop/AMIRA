/**
 * Contrat avec le back-end Amira (voir docs/API.md).
 * Le front ne connaît que ces interfaces : brancher le vrai serveur = renseigner VITE_AMIRA_API_URL dans .env, puis reconstruire.
 */

/** 'fr', 'en' ou le code de la langue cible (languages.ts). */
export type SourceLang = string;
export type TargetLang = string;
/** Variété de la langue cible (liste dans backend/languages/<code>/language.json). */
export type Variety = string;
export type CategoryHint = 'label' | 'instruction' | 'fees' | 'security_warning' | 'error';
export type SegmentStatus = 'validated' | 'machine' | 'uncertain';
export type SegmentOrigin = 'memory' | 'template' | 'llm';

export interface Capabilities {
  translate: boolean;
  tts: boolean;
  stt: boolean;
  languages: string[];
  varietes: string[];
}

export interface Health {
  ok: boolean;
  version?: string;
}

export interface TranslateSegmentIn {
  id: string;
  /** Texte DÉJÀ MASQUÉ : aucune donnée personnelle, seulement des marqueurs {N0}, {B0}… */
  text: string;
  categoryHint?: CategoryHint;
  placeholders: string[];
}

export interface TranslateRequest {
  requestId: string;
  source: SourceLang;
  target: TargetLang;
  variety: Variety | null;
  segments: TranslateSegmentIn[];
}

export interface TranslateSegmentOut {
  id: string;
  text: string;
  status: SegmentStatus;
  confidence: number;
  origin: SegmentOrigin;
}

export interface TranslateResponse {
  requestId: string;
  engineVersion: string;
  latencyMs: number;
  segments: TranslateSegmentOut[];
}

export interface TtsRequest {
  text: string;
  language: TargetLang | 'fr' | 'en';
  speed?: number;
  /** Clé stable du segment lu : le serveur peut renvoyer l'enregistrement d'un locuteur natif. */
  segmentKey?: string;
}

export interface TtsResult {
  /** Audio encodé en base64 (passe par la messagerie de l'extension) ; null = synthèse du navigateur. */
  audioBase64: string | null;
  mimeType: string | null;
  voice: 'recorded' | 'synthetic';
}

export interface FeedbackRequest {
  segmentId: string;
  originalMasked: string;
  shown: string;
  suggestion: string;
}

export type ApiErrorCode =
  | 'RATE_LIMITED'
  | 'UNAVAILABLE'
  | 'TIMEOUT'
  | 'BAD_REQUEST'
  | 'UNSUPPORTED_LANGUAGE'
  // codes côté client (pas renvoyés par le serveur)
  | 'NOT_CONFIGURED'
  | 'NETWORK'
  | 'BAD_RESPONSE';

export class ApiError extends Error {
  constructor(
    public code: ApiErrorCode,
    message: string,
    public httpStatus?: number,
    public retryAfterMs?: number,
    public durationMs?: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export interface AmiraApi {
  health(): Promise<Health>;
  capabilities(): Promise<Capabilities>;
  translate(req: TranslateRequest): Promise<TranslateResponse>;
  tts(req: TtsRequest): Promise<TtsResult>;
  stt(audioBase64: string, mimeType: string, language: string): Promise<{ text: string }>;
  feedback(req: FeedbackRequest): Promise<void>;
}

export const DEFAULT_TIMEOUT_MS = 8000;

function bytesToBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let bin = '';
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}

function base64ToBlob(b64: string, mime: string): Blob {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}

/** Client HTTP du vrai serveur. Aucun secret : l'authentification éventuelle se fait côté serveur. */
export class HttpApi implements AmiraApi {
  private base: string;

  constructor(baseUrl: string, private timeoutMs = DEFAULT_TIMEOUT_MS) {
    this.base = baseUrl.replace(/\/+$/, '');
  }

  private async request(path: string, init: RequestInit = {}): Promise<Response> {
    if (!this.base) throw new ApiError('NOT_CONFIGURED', 'Aucune URL de serveur');
    const ctrl = new AbortController();
    const t0 = performance.now();
    const timer = setTimeout(() => ctrl.abort(), this.timeoutMs);
    let res: Response;
    try {
      res = await fetch(this.base + path, {
        ...init,
        signal: ctrl.signal,
        credentials: 'omit',
        headers: { Accept: 'application/json', ...(init.body && typeof init.body === 'string' ? { 'Content-Type': 'application/json' } : {}), ...init.headers },
      });
    } catch (e) {
      const durationMs = Math.round(performance.now() - t0);
      if ((e as Error).name === 'AbortError') throw new ApiError('TIMEOUT', 'Délai dépassé', undefined, undefined, durationMs);
      throw new ApiError('NETWORK', 'Serveur injoignable', undefined, undefined, durationMs);
    } finally {
      clearTimeout(timer);
    }
    if (!res.ok) {
      const durationMs = Math.round(performance.now() - t0);
      let code: ApiErrorCode = res.status === 429 ? 'RATE_LIMITED' : res.status >= 500 ? 'UNAVAILABLE' : 'BAD_REQUEST';
      let message = `HTTP ${res.status}`;
      let retryAfterMs: number | undefined;
      try {
        const body = await res.json();
        if (body?.error?.code) code = body.error.code;
        if (body?.error?.message) message = String(body.error.message).slice(0, 200);
        if (typeof body?.error?.retryAfterMs === 'number') retryAfterMs = body.error.retryAfterMs;
      } catch {
        /* corps non JSON : on garde le code HTTP */
      }
      throw new ApiError(code, message, res.status, retryAfterMs, durationMs);
    }
    return res;
  }

  private async json<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await this.request(path, init);
    try {
      return (await res.json()) as T;
    } catch {
      throw new ApiError('BAD_RESPONSE', 'Réponse illisible', res.status);
    }
  }

  async health(): Promise<Health> {
    const h = await this.json<Partial<Health>>('/v1/health');
    return { ok: h.ok !== false, version: h.version };
  }

  async capabilities(): Promise<Capabilities> {
    const c = await this.json<Partial<Capabilities>>('/v1/capabilities');
    return {
      translate: !!c.translate,
      tts: !!c.tts,
      stt: !!c.stt,
      languages: Array.isArray(c.languages) ? c.languages : [],
      varietes: Array.isArray(c.varietes) ? c.varietes : [],
    };
  }

  async translate(req: TranslateRequest): Promise<TranslateResponse> {
    const r = await this.json<TranslateResponse>('/v1/translate', { method: 'POST', body: JSON.stringify(req) });
    if (!r || !Array.isArray(r.segments)) throw new ApiError('BAD_RESPONSE', 'Réponse sans segments');
    return r;
  }

  async tts(req: TtsRequest): Promise<TtsResult> {
    const res = await this.request('/v1/tts', { method: 'POST', body: JSON.stringify(req), headers: { Accept: 'audio/*' } });
    const voice = res.headers.get('X-Amira-Voice') === 'recorded' ? 'recorded' : 'synthetic';
    const mimeType = res.headers.get('Content-Type') || 'audio/mpeg';
    return { audioBase64: bytesToBase64(await res.arrayBuffer()), mimeType, voice };
  }

  async stt(audioBase64: string, mimeType: string, language: string): Promise<{ text: string }> {
    const res = await this.request(`/v1/stt?language=${encodeURIComponent(language)}`, {
      method: 'POST',
      body: base64ToBlob(audioBase64, mimeType),
      headers: { 'Content-Type': mimeType },
    });
    const j = await res.json();
    return { text: String(j.text ?? '') };
  }

  async feedback(req: FeedbackRequest): Promise<void> {
    await this.request('/v1/feedback', { method: 'POST', body: JSON.stringify(req) });
  }
}

export function newRequestId(): string {
  const a = new Uint8Array(8);
  crypto.getRandomValues(a);
  return Array.from(a, (b) => b.toString(16).padStart(2, '0')).join('');
}
