/**
 * Serveur simulé (mode démonstration).
 * RÈGLE : il ne fabrique JAMAIS de faux fulfulde. Il renvoie le texte source préfixé de « ⟦FF⟧ »
 * pour montrer la chaîne de bout en bout, avec des statuts et des pannes simulés.
 */
import { TARGET } from '../languages';
import {
  AmiraApi,
  ApiError,
  Capabilities,
  FeedbackRequest,
  Health,
  TranslateRequest,
  TranslateResponse,
  TranslateSegmentOut,
  TtsRequest,
  TtsResult,
} from './api';

export type MockScenario = 'normal' | 'http500' | 'http429' | 'timeout' | 'offline' | 'brokenMarkers';

export const MOCK_PREFIX = '⟦FF⟧';

export interface MockOptions {
  scenario?: MockScenario;
  latencyMs?: number;
  timeoutMs?: number;
}

/** Hachage stable pour des statuts reproductibles d'un appel à l'autre. */
function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export class MockApi implements AmiraApi {
  scenario: MockScenario;
  latencyMs: number;
  timeoutMs: number;
  readonly feedbackLog: FeedbackRequest[] = [];

  constructor(opts: MockOptions = {}) {
    this.scenario = opts.scenario ?? 'normal';
    this.latencyMs = opts.latencyMs ?? 120;
    this.timeoutMs = opts.timeoutMs ?? 8000;
  }

  private async fail(): Promise<void> {
    switch (this.scenario) {
      case 'http500':
        await sleep(this.latencyMs);
        throw new ApiError('UNAVAILABLE', 'Erreur interne simulée', 500, undefined, this.latencyMs);
      case 'http429':
        await sleep(this.latencyMs);
        throw new ApiError('RATE_LIMITED', 'Trop de requêtes (simulé)', 429, 3000, this.latencyMs);
      case 'timeout':
        await sleep(Math.min(this.timeoutMs, 1500));
        throw new ApiError('TIMEOUT', 'Délai dépassé (simulé)', undefined, undefined, this.timeoutMs);
      case 'offline':
        throw new ApiError('NETWORK', 'Réseau coupé (simulé)', undefined, undefined, 0);
      default:
        await sleep(this.latencyMs);
    }
  }

  async health(): Promise<Health> {
    await this.fail();
    return { ok: true, version: 'mock-0.1' };
  }

  async capabilities(): Promise<Capabilities> {
    await this.fail();
    return { translate: true, tts: true, stt: false, languages: ['fr', 'en', TARGET.code], varietes: [TARGET.defaultVariety] };
  }

  async translate(req: TranslateRequest): Promise<TranslateResponse> {
    const t0 = performance.now();
    await this.fail();
    const segments: TranslateSegmentOut[] = req.segments.map((s) => {
      const h = hash(s.text);
      // Avertissements de sécurité : le mock les considère « validés » (traduction relue fictive)
      // pour démontrer l'affichage ; le reste se répartit entre automatique et incertain.
      const status = s.categoryHint === 'security_warning' ? 'validated' : h % 10 < 6 ? 'machine' : h % 10 < 8 ? 'validated' : 'uncertain';
      const confidence = status === 'validated' ? 0.97 : status === 'machine' ? 0.6 + (h % 30) / 100 : 0.3;
      let text = `${MOCK_PREFIX} ${s.text}`;
      if (this.scenario === 'brokenMarkers' && s.placeholders.length) text = text.replace(s.placeholders[0], '');
      return { id: s.id, text, status, confidence, origin: status === 'validated' ? 'memory' : 'llm' };
    });
    return { requestId: req.requestId, engineVersion: 'mock-0.1', latencyMs: Math.round(performance.now() - t0), segments };
  }

  async tts(_req: TtsRequest): Promise<TtsResult> {
    await this.fail();
    // Pas d'audio fabriqué : le panneau utilise la synthèse vocale du navigateur, étiquetée comme telle.
    return { audioBase64: null, mimeType: null, voice: 'synthetic' };
  }

  async stt(): Promise<{ text: string }> {
    throw new ApiError('UNSUPPORTED_LANGUAGE', 'Dictée non disponible en démonstration');
  }

  async feedback(req: FeedbackRequest): Promise<void> {
    await this.fail();
    this.feedbackLog.push(req);
  }
}
