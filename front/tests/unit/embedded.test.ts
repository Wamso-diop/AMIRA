import { describe, expect, it, vi } from 'vitest';
import vectors from '../fixtures/embedded_vectors.json';
import audio from '../../src/data/audio.json';
import memory from '../../src/data/memory.json';
import { ApiError, type AmiraApi, type TranslateRequest } from '../../src/services/api';
import { EmbeddedApi, fromMemory } from '../../src/services/embedded';

type Vec = { source: string; target: string; variety: string; text: string; expected: string | null };
const VEC = vectors as Vec[];
const table = (v: Pick<Vec, 'source' | 'target' | 'variety'>) => (memory.tables as Record<string, Record<string, string>>)[`${v.source}>${v.target}|${v.variety}`] ?? {};
const known = VEC.find((v) => v.expected !== null && v.source === 'fr' && v.target === memory.language && !/[{}]/.test(v.text))!;
const unknown = VEC.find((v) => v.expected === null && v.source === 'fr' && v.target === memory.language && v.text.length > 12 && !/[{}\d]/.test(v.text))!;

const req = (texts: string[], source = 'fr', target = memory.language): TranslateRequest => ({
  requestId: 'r1', source, target, variety: memory.variety,
  segments: texts.map((text, i) => ({ id: `s${i}`, text, placeholders: [] })),
});

function fakeServer(impl?: Partial<AmiraApi>) {
  const api = {
    health: vi.fn(), capabilities: vi.fn(), stt: vi.fn(), feedback: vi.fn(async () => undefined),
    translate: vi.fn(async (r: TranslateRequest) => ({ requestId: r.requestId, engineVersion: 'srv', latencyMs: 1,
      segments: r.segments.map((s) => ({ id: s.id, text: `[serveur] ${s.text}`, status: 'machine' as const, confidence: 0.8, origin: 'llm' as const })) })),
    tts: vi.fn(async () => ({ audioBase64: 'U0VSVkVVUg==', mimeType: 'audio/mp4', voice: 'recorded' as const })),
    ...impl,
  };
  return api as unknown as AmiraApi & typeof api;
}

describe('mémoire embarquée : mêmes réponses que le vrai serveur', () => {
  it(`donne la réponse du serveur sur ${VEC.length} requêtes (casse, ponctuation, espaces, apostrophes, fin de segment, marqueurs)`, () => {
    const bad = VEC.filter((v) => fromMemory(table(v), v.text) !== v.expected);
    expect(bad.slice(0, 3)).toEqual([]);
  });
});

describe('EmbeddedApi : l\'extension agit seule', () => {
  it('annonce ce qu\'elle sait faire : traduire et lire, sans dictée', async () => {
    const api = new EmbeddedApi();
    expect((await api.health()).ok).toBe(true);
    const c = await api.capabilities();
    expect(c).toMatchObject({ translate: true, tts: true, stt: false });
    expect(c.languages).toContain(memory.language);
  });

  it('traduit un texte connu : validated, confiance 1, origine mémoire', async () => {
    const res = await new EmbeddedApi().translate(req([known.text]));
    expect(res.segments[0]).toMatchObject({ id: 's0', text: known.expected, status: 'validated', confidence: 1, origin: 'memory' });
  });

  it('dans le doute (texte inconnu) : uncertain et texte source, jamais validated', async () => {
    const res = await new EmbeddedApi().translate(req([unknown.text]));
    expect(res.segments[0]).toMatchObject({ text: unknown.text, status: 'uncertain', confidence: 0 });
  });

  it('un texte masqué (avec un marqueur {N0}) n\'est pas pris pour une valeur sensible : il est traduit par la mémoire', async () => {
    const withMarker = VEC.find((v) => v.expected !== null && v.source === 'fr' && v.target === memory.language && /\{N0\}/.test(v.text) && !/[^{}]\d/.test(v.text.replace(/\{N\d+\}/g, '')))!;
    const res = await new EmbeddedApi().translate(req([withMarker.text]));
    expect(res.segments[0]).toMatchObject({ text: withMarker.expected, status: 'validated' });
  });

  it('refuse un sens non autorisé, et un texte qui contient encore une valeur sensible n\'est jamais traité', async () => {
    await expect(new EmbeddedApi().translate(req([known.text], 'fr', 'en'))).rejects.toMatchObject({ code: 'UNSUPPORTED_LANGUAGE' });
    const srv = fakeServer();
    const res = await new EmbeddedApi(srv).translate(req(['Solde de 250 000 FCFA', 'Total 12']));
    expect(res.segments.map((s) => s.status)).toEqual(['uncertain', 'uncertain']);
    expect(srv.translate).not.toHaveBeenCalled();
  });

  it('un texte connu ne part jamais au serveur ; seul l\'inconnu y va, et sa réponse reste « machine »', async () => {
    const srv = fakeServer();
    const res = await new EmbeddedApi(srv).translate(req([known.text, unknown.text]));
    const sent = (srv.translate as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as TranslateRequest;
    expect(sent.segments.map((x) => x.text)).toEqual([unknown.text]);
    expect(res.segments[0]).toMatchObject({ status: 'validated', origin: 'memory' });
    expect(res.segments[1]).toMatchObject({ id: 's1', status: 'machine', origin: 'llm' });
  });

  it('serveur en panne : uncertain, et il n\'est pas réinterrogé aussitôt', async () => {
    let t = 1000;
    const srv = fakeServer({ translate: vi.fn(async () => { throw new ApiError('NETWORK', 'injoignable'); }) });
    const api = new EmbeddedApi(srv, () => t);
    expect((await api.translate(req([unknown.text]))).segments[0].status).toBe('uncertain');
    await api.translate(req([unknown.text]));
    expect(srv.translate).toHaveBeenCalledTimes(1);
    t += 31_000;
    await api.translate(req([unknown.text]));
    expect(srv.translate).toHaveBeenCalledTimes(2);
  });

  it('un serveur qui répond uncertain (frais ou avertissement sans version validée) reste uncertain', async () => {
    const srv = fakeServer({ translate: vi.fn(async (r: TranslateRequest) => ({ requestId: r.requestId, engineVersion: 's', latencyMs: 1,
      segments: r.segments.map((s) => ({ id: s.id, text: s.text, status: 'uncertain' as const, confidence: 0, origin: 'llm' as const })) })) });
    const res = await new EmbeddedApi(srv).translate(req([unknown.text]));
    expect(res.segments[0].status).toBe('uncertain');
  });
});

describe('EmbeddedApi : la voix des natifs est dans l\'extension', () => {
  const keys = audio.keys as Record<string, string>;
  const [key, file] = Object.entries(keys)[0];

  it('joue l\'enregistrement du natif pour une clé connue, sans réseau', async () => {
    const load = vi.fn(async () => new Uint8Array([1, 2, 3]).buffer);
    const r = await new EmbeddedApi(null, Date.now, load).tts({ text: 'x', language: memory.language, segmentKey: key });
    expect(load).toHaveBeenCalledWith(file);
    expect(r).toEqual({ audioBase64: 'AQID', mimeType: 'audio/mp4', voice: 'recorded' });
  });

  it('clé inconnue sans serveur : pas d\'audio (le panneau le dit), avec serveur : la voix du serveur', async () => {
    const load = vi.fn();
    expect(await new EmbeddedApi(null, Date.now, load).tts({ text: 'x', language: memory.language, segmentKey: 'kffffffff' })).toMatchObject({ audioBase64: null });
    const srv = fakeServer();
    expect((await new EmbeddedApi(srv, Date.now, load).tts({ text: 'x', language: memory.language, segmentKey: 'kffffffff' })).audioBase64).toBe('U0VSVkVVUg==');
    expect(load).not.toHaveBeenCalled();
  });
});

describe('EmbeddedApi : ce qui exige un serveur', () => {
  it('le signalement sans serveur le dit au lieu de faire semblant', async () => {
    await expect(new EmbeddedApi().feedback({ segmentId: 's', originalMasked: 'a', shown: 'b', suggestion: 'c' })).rejects.toMatchObject({ code: 'UNAVAILABLE' });
    const srv = fakeServer();
    await new EmbeddedApi(srv).feedback({ segmentId: 's', originalMasked: 'a', shown: 'b', suggestion: 'c' });
    expect(srv.feedback).toHaveBeenCalled();
  });
});
