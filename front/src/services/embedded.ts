/**
 * Mode autonome : l'extension agit SEULE, avec la mémoire validée par le locuteur natif et ses voix, embarquées dans le paquet
 * (données exportées par backend/tools/export_extension_data.py). Aucun réseau.
 *
 * Les règles sont celles du serveur (backend/amira/db.py, markers.py, services/translator.py), portées à l'identique : un test
 * compare ce code aux réponses du vrai serveur sur plusieurs milliers de requêtes (tests/unit/embedded.test.ts).
 *   - « validated » : uniquement une entrée de la mémoire relue par un natif ; jamais une sortie de modèle (P2) ;
 *   - dans le doute : « uncertain » et le texte reçu (P5) ; frais et avertissements : mémoire seulement (P3).
 * Si un serveur est configuré (build « hybride »), il n'est interrogé que pour ce que la mémoire ne connaît pas.
 */
import audio from '../data/audio.json';
import memory from '../data/memory.json';
import { TARGET } from '../languages';
import {
  ApiError,
  bytesToBase64,
  type AmiraApi,
  type Capabilities,
  type FeedbackRequest,
  type Health,
  type TranslateRequest,
  type TranslateResponse,
  type TranslateSegmentOut,
  type TtsRequest,
  type TtsResult,
} from './api';

// ---------------------------------------------------------------------------------------------------------------- marqueurs
const MARKER_RE = /\{\/?[NBE]\d+\}/g;
const N_RE = /\{N\d+\}/g;
const TAG_RE = /\{(\/?)B(\d+)\}/g;
const BRACE_RE = /\{[^{}]*\}/g;
// Fin de segment sans mot à traduire : numéros masqués, codes en capitales (« CM »), ponctuation (TAIL_RE du serveur ;
// \b de Python est Unicode, d'où les lookarounds).
const TAIL_RE = /(?:[\s:,;!?/()#+.\-–—]|\{N\d+\}|(?<![\p{L}\p{N}_])[A-Z]{1,4}(?![\p{L}\p{N}_]))+$/u;
const TRAILING_PUNCT_RE = /[\s.!?:;,…]+$/u;

const counts = (s: string, re: RegExp) => {
  const m = new Map<string, number>();
  for (const x of s.match(re) ?? []) m.set(x, (m.get(x) ?? 0) + 1);
  return m;
};
const sameCounts = (a: Map<string, number>, b: Map<string, number>) => a.size === b.size && [...a].every(([k, v]) => b.get(k) === v);

function wellNested(text: string): boolean {
  const stack: string[] = [];
  for (const [, closing, n] of text.matchAll(TAG_RE)) {
    if (!closing) stack.push(n);
    else if (stack.pop() !== n) return false;
  }
  return stack.length === 0;
}

/** markers_ok du serveur : mêmes marqueurs, même nombre de fois, {B} bien imbriqués, autres accolades intactes. */
function markersOk(source: string, translated: string): boolean {
  const n = (s: string, c: string) => s.split(c).length - 1;
  return (
    sameCounts(counts(source, MARKER_RE), counts(translated, MARKER_RE)) &&
    wellNested(translated) &&
    sameCounts(counts(source, BRACE_RE), counts(translated, BRACE_RE)) &&
    n(source, '{') === n(translated, '{') &&
    n(source, '}') === n(translated, '}')
  );
}

/** Renumérote les {N} dans l'ordre d'apparition ; renvoie le texte canonique et la table canonique → origine. */
function canonicalize(masked: string): [string, Map<string, string>] {
  const toCanon = new Map<string, string>();
  for (const m of masked.match(N_RE) ?? []) if (!toCanon.has(m)) toCanon.set(m, `{N${toCanon.size}}`);
  return [masked.replace(N_RE, (m) => toCanon.get(m)!), new Map([...toCanon].map(([o, c]) => [c, o]))];
}

const restore = (text: string, table: Map<string, string>) => text.replace(N_RE, (m) => table.get(m) ?? m);

/** memory_key du serveur : {N} renumérotés, NFC, minuscules, apostrophes droites, espaces simples, ponctuation finale retirée. */
function memoryKey(masked: string): string {
  let text = canonicalize(masked)[0].normalize('NFC').replace(/[’‘ʼ`´]/g, "'").replace(/…/g, '...');
  text = text.replace(/«\s+/g, '«').replace(/\s+([:;!?»])/g, '$1');
  text = text.replace(/\s+/g, ' ').trim().toLowerCase();
  text = text.replace(/\{(\/?)([nbe])(\d+)\}/g, (_, c, k, d) => `{${c}${k.toUpperCase()}${d}}`);
  return text.replace(TRAILING_PUNCT_RE, '');
}

/** from_memory du serveur : traduction validée du texte entier, sinon du début quand la fin n'est que numéros masqués et codes. */
export function fromMemory(table: Record<string, string>, text: string): string | null {
  const tail = TAIL_RE.exec(text);
  const tries: [string, string][] = [[text, '']];
  if (tail && tail.index > 0 && tail[0].includes('{N')) tries.push([text.slice(0, tail.index), tail[0]]);
  for (const [head, rest] of tries) {
    const hit = table[memoryKey(head)];
    if (hit === undefined) continue;
    let translated = restore(hit, canonicalize(head)[1]);
    if (rest) translated = translated.trimEnd() + rest;
    if (markersOk(text, translated)) return translated;
  }
  return null;
}

// ---------------------------------------------------------------------------------------------------------------- garde
// shortcut: garde simplifiée côté extension (le masquage a déjà eu lieu avant l'appel) ; la garde complète du serveur reste
// la référence, y compris ses règles sur les chiffres Unicode et les IBAN. À aligner si le serveur durcit la sienne.
const SENSITIVE_RE = /\p{Nd}|[€$£₦¥]|\b(?:FCFA|F\s?CFA|CFA|XAF|XOF|francs?)\b|[\w.+-]+@[\w-]+\.[\w.-]+/iu;

// ---------------------------------------------------------------------------------------------------------------- client
const DIRECTIONS = new Set([`fr>${TARGET.code}`, `en>${TARGET.code}`, `${TARGET.code}>fr`, `${TARGET.code}>en`]);
const SERVER_PAUSE_MS = 30_000; // un serveur injoignable n'est pas réinterrogé à chaque phrase
const tables = memory.tables as Record<string, Record<string, string>>;
const voices = audio.keys as Record<string, string>;

const uncertain = (id: string, text: string): TranslateSegmentOut => ({ id, text, status: 'uncertain', confidence: 0, origin: 'llm' });

/** Lit un fichier audio du paquet de l'extension. */
const loadPackagedAudio = async (file: string): Promise<ArrayBuffer> => (await fetch(chrome.runtime.getURL(`audio/${file}`))).arrayBuffer();

export class EmbeddedApi implements AmiraApi {
  private serverDownUntil = 0;

  /** server : serveur facultatif (build hybride), consulté seulement pour ce que la mémoire ne connaît pas. */
  constructor(
    private server: AmiraApi | null = null,
    private now: () => number = Date.now,
    private loadAudio: (file: string) => Promise<ArrayBuffer> = loadPackagedAudio,
  ) {}

  async health(): Promise<Health> {
    return { ok: true, version: `embedded-${memory.language}` };
  }

  async capabilities(): Promise<Capabilities> {
    return { translate: true, tts: true, stt: false, languages: ['fr', 'en', memory.language], varietes: [memory.variety] };
  }

  private serverUsable() {
    return this.server !== null && this.now() >= this.serverDownUntil;
  }

  async translate(req: TranslateRequest): Promise<TranslateResponse> {
    const t0 = this.now();
    const dir = `${req.source}>${req.target}`;
    if (!DIRECTIONS.has(dir)) throw new ApiError('UNSUPPORTED_LANGUAGE', 'Sens de traduction non pris en charge');
    const variety = req.target === memory.language ? req.variety || memory.variety : '';
    const table = tables[`${dir}|${variety}`] ?? {};
    const out: (TranslateSegmentOut | null)[] = req.segments.map((s) => {
      if (SENSITIVE_RE.test(s.text.replace(MARKER_RE, ' '))) return uncertain(s.id, s.text); // les marqueurs {N0} contiennent un chiffre : on les retire d'abord
      const text = fromMemory(table, s.text);
      return text === null ? null : { id: s.id, text, status: 'validated', confidence: 1, origin: 'memory' };
    });
    const todo = req.segments.filter((_, i) => out[i] === null);
    if (todo.length && this.serverUsable()) {
      try {
        const res = await this.server!.translate({ ...req, segments: todo });
        const byId = new Map(res.segments.map((s) => [s.id, s]));
        req.segments.forEach((s, i) => {
          const r = byId.get(s.id);
          if (out[i] === null && r) out[i] = r;
        });
      } catch {
        this.serverDownUntil = this.now() + SERVER_PAUSE_MS;
      }
    }
    return {
      requestId: req.requestId,
      engineVersion: `embedded-${memory.language}`,
      latencyMs: Math.round(this.now() - t0),
      segments: req.segments.map((s, i) => out[i] ?? uncertain(s.id, s.text)),
    };
  }

  async tts(req: TtsRequest): Promise<TtsResult> {
    const file = req.language === memory.language && req.segmentKey ? voices[req.segmentKey] : undefined;
    if (file) return { audioBase64: bytesToBase64(await this.loadAudio(file)), mimeType: 'audio/mp4', voice: 'recorded' };
    if (this.serverUsable()) {
      try {
        return await this.server!.tts(req);
      } catch {
        this.serverDownUntil = this.now() + SERVER_PAUSE_MS;
      }
    }
    return { audioBase64: null, mimeType: null, voice: 'synthetic' }; // le panneau dit qu'il n'y a pas de voix pour ce passage
  }

  async stt(): Promise<{ text: string }> {
    throw new ApiError('BAD_REQUEST', 'Dictée indisponible');
  }

  async feedback(req: FeedbackRequest): Promise<void> {
    if (!this.server) throw new ApiError('UNAVAILABLE', 'Signalement indisponible sans serveur');
    await this.server.feedback(req);
  }
}
