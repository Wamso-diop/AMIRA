// Lecture automatique des messages d'erreur de la page. Vit dans l'App (toujours montée) : elle ne dépend donc pas
// de l'onglet affiché. Le message arrive avec la clé de son enregistrement : le serveur sert la voix du locuteur natif.
import { useEffect } from 'react';
import { isTarget, TARGET } from '../languages';
import type { Settings } from '../services/settings';
import type { ContentEvent } from '../shared/messages';
import { play, type Passage } from './player';

/** Langue lue : celle de la traduction affichée (langue cible, ou français/anglais si la page est dans la langue cible). */
export const readLangFor = (pageLang: string | undefined, settings: Pick<Settings, 'returnLang'>) =>
  isTarget(pageLang) ? settings.returnLang : TARGET.code;

export const BATCH_MS = 350; // des erreurs affichées ensemble sont lues à la suite, au lieu de s'interrompre
export const REPEAT_MS = 30_000; // la même erreur n'est pas relue en boucle

interface Timers {
  now: () => number;
  setTimer: (f: () => void, ms: number) => unknown;
  clearTimer: (t: unknown) => void;
}
const REAL: Timers = { now: Date.now, setTimer: (f, ms) => setTimeout(f, ms), clearTimer: (t) => clearTimeout(t as number) };

export function createErrorReader(read: (passages: Passage[]) => void, timers: Timers = REAL) {
  let queue: Passage[] = [];
  let timer: unknown;
  const seen = new Map<string, number>();
  return {
    add(text: string, key?: string) {
      const id = key ?? text;
      const t = timers.now();
      if (t - (seen.get(id) ?? -Infinity) < REPEAT_MS) return;
      seen.set(id, t);
      queue.push({ text, key });
      timers.clearTimer(timer);
      timer = timers.setTimer(() => {
        const batch = queue;
        queue = [];
        read(batch);
      }, BATCH_MS);
    },
    cancel() {
      timers.clearTimer(timer);
      queue = [];
    },
  };
}

export function useAutoReadErrors(settings: Settings | null | undefined, ttsAvailable: boolean, pageLang: string | undefined) {
  const on = !!settings?.autoReadWarnings && ttsAvailable;
  const speed = settings?.ttsSpeed ?? 1;
  const lang = settings ? readLangFor(pageLang, settings) : TARGET.code;
  useEffect(() => {
    if (!on) return;
    const reader = createErrorReader((passages) => void play(passages, lang, speed).catch(() => undefined));
    const onMsg = (msg: ContentEvent) => {
      if (msg?.type === 'amira:error') reader.add(msg.text, msg.key);
    };
    chrome.runtime.onMessage.addListener(onMsg);
    return () => {
      chrome.runtime.onMessage.removeListener(onMsg);
      reader.cancel();
    };
  }, [on, lang, speed]);
}
