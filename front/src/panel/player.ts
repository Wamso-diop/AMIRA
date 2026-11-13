/**
 * Lecteur partagé : enregistrement d'un locuteur natif servi par /v1/tts. Sans enregistrement pour un
 * passage, un message le dit (aucune voix de synthèse) et la lecture passe au suivant.
 * Les textes reçus sont déjà masqués : les marqueurs {N0}… sont retirés avant lecture.
 */
import type { TtsResult } from '../services/api';
import type { TtsResultMsg } from '../shared/messages';
import { bg } from './bridge';

export type PlayerState = {
  status: 'idle' | 'loading' | 'playing' | 'paused';
  voice: TtsResult['voice'] | null;
  error: string | null;
  /** Passage en cours (0 = premier) et nombre total de passages de la lecture. */
  index: number;
  total: number;
  /** Identifiant du segment de page en cours de lecture (pour l'entourer sur la page). */
  currentId: string | null;
  /** Le dernier passage demandé n'a pas encore d'enregistrement. */
  missing: boolean;
};

/** Un passage à lire : texte masqué, et si possible l'identifiant et la clé stable du segment. */
export type Passage = string | { text: string; id?: string; key?: string };

export const IDLE: PlayerState = { status: 'idle', voice: null, error: null, index: 0, total: 0, currentId: null, missing: false };
/** Temps laissé pour lire le message « pas d'enregistrement » avant le passage suivant. */
const MISSING_PAUSE_MS = 1500;
let state: PlayerState = IDLE;
const subs = new Set<(s: PlayerState) => void>();
let audio: HTMLAudioElement | null = null;
let wait: ReturnType<typeof setTimeout> | null = null;
let queue: { text: string; id?: string; key?: string }[] = [];
let total = 0;
let token = 0;
let rate = 1;
let lang = 'ff';

function set(p: Partial<PlayerState>) {
  state = { ...state, ...p };
  subs.forEach((f) => f(state));
}

export function subscribe(f: (s: PlayerState) => void): () => void {
  subs.add(f);
  f(state);
  return () => subs.delete(f);
}

const speakable = (s: string) => s.replace(/\{\/?[NBE]\d+\}/g, ' ').replace(/⟦FF⟧/g, '').replace(/\s+/g, ' ').trim();

export async function play(passages: Passage[], language: string, speed: number): Promise<void> {
  stop();
  const my = ++token;
  queue = passages
    .map((p) => (typeof p === 'string' ? { text: p } : p))
    .map((p) => ({ ...p, text: speakable(p.text) }))
    .filter((p) => p.text);
  total = queue.length;
  rate = speed;
  lang = language;
  if (!queue.length) return;
  set({ status: 'loading', error: null, index: 0, total, currentId: queue[0].id ?? null, missing: false });
  await next(my);
}

async function next(my: number) {
  if (my !== token) return;
  const item = queue.shift();
  if (!item) return set({ status: 'idle', currentId: null, index: 0, total: 0 });
  const { text } = item;
  set({ index: total - queue.length - 1, currentId: item.id ?? null });
  const res = await bg<TtsResultMsg>({ type: 'amira:tts', req: { text, language: lang as 'ff', speed: rate, segmentKey: item.key } }).catch(
    () => ({ ok: false, code: 'CLIENT_ERROR', message: '' }) as TtsResultMsg,
  );
  if (my !== token) return;
  if (!res.ok) return set({ status: 'idle', error: res.code, currentId: null });
  const r = res.data;
  if (r.audioBase64 && r.mimeType) {
    set({ voice: r.voice, status: 'playing', missing: false });
    audio = new Audio(`data:${r.mimeType};base64,${r.audioBase64}`);
    audio.playbackRate = rate;
    audio.onended = () => void next(my);
    audio.onerror = () => set({ status: 'idle', error: 'AUDIO', currentId: null });
    await audio.play().catch(() => set({ status: 'idle', error: 'AUDIO', currentId: null }));
  } else {
    audio = null;
    set({ voice: null, status: 'playing', missing: true });
    wait = setTimeout(() => void next(my), MISSING_PAUSE_MS);
  }
}

export function pause() {
  if (state.status !== 'playing') return;
  audio?.pause();
  if (wait) clearTimeout(wait);
  set({ status: 'paused' });
}

export function resume() {
  if (state.status !== 'paused') return;
  if (audio) void audio.play();
  else if (state.missing) wait = setTimeout(() => void next(token), MISSING_PAUSE_MS);
  set({ status: 'playing' });
}

export function stop() {
  token++;
  queue = [];
  if (wait) clearTimeout(wait);
  if (audio) {
    audio.pause();
    audio = null;
  }
  set({ status: 'idle', currentId: null, index: 0, total: 0 });
}

export function setRate(r: number) {
  rate = r;
  if (audio) audio.playbackRate = r;
}
