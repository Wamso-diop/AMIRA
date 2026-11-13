/**
 * Banc d'essai (tests Playwright uniquement) : le moteur branché directement sur le mock,
 * sans chrome.*. N'est jamais inclus dans l'extension.
 */
import { TARGET } from '../languages';
import { Engine } from './engine';
import { MockApi, type MockScenario } from '../services/mock';
import type { LogEntry } from '../services/log';
import type { PageStats } from '../shared/messages';

const api = new MockApi({ latencyMs: 20 });
const logs: Partial<LogEntry>[] = [];
const sentTexts: string[] = [];
const requests: { source: string; target: string }[] = [];
let lastStats: PageStats | null = null;

const engine = new Engine({
  doc: document,
  settings: { returnLang: 'fr', variety: TARGET.defaultVariety, display: 'replace', prudence: false, confidenceThreshold: 0, extraNames: [] },
  translate: async (req) => {
    req.segments.forEach((s) => sentTexts.push(s.text));
    requests.push({ source: req.source, target: req.target });
    try {
      const data = await api.translate(req);
      return { ok: true, data: { ...data, fromCache: 0 } };
    } catch (e) {
      const err = e as { code: string; message: string };
      return { ok: false, code: err.code, message: err.message };
    }
  },
  log: (e) => logs.push(e),
  onStats: (s) => (lastStats = s),
  debounceMs: 60,
});

const harness = {
  engine,
  logs,
  sentTexts,
  requests,
  enable: () => engine.enable(),
  disable: () => engine.disable(),
  showOriginal: (on: boolean) => engine.setShowOriginal(on),
  setScenario: (s: MockScenario) => (api.scenario = s),
  stats: () => engine.stats(),
  lastStats: () => lastStats,
  /** Détail par segment pour les mesures de test (reste dans la page de test). */
  segments: () =>
    [...engine.segs.values()].map((s) => ({
      id: s.id,
      kind: s.kind,
      state: s.state,
      reason: s.reason,
      category: s.category,
      original: s.original,
      masked: s.masked,
      values: [...s.values.values()],
      placeholders: s.placeholders,
      translation: s.translation,
    })),
  idle: () =>
    new Promise<void>((resolve) => {
      const check = () => {
        const st = engine.stats();
        if (st.pending === 0) resolve();
        else setTimeout(check, 25);
      };
      setTimeout(check, 120);
    }),
};

(window as unknown as { Amira: typeof harness }).Amira = harness;
