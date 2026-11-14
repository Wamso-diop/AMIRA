import { describe, expect, it, vi } from 'vitest';
import { BATCH_MS, createErrorReader, readLangFor, REPEAT_MS } from '../../src/panel/autoRead';
import { DEFAULT_SETTINGS, normalizeSettings } from '../../src/services/settings';

function lecteur() {
  let t = 0;
  const timers: { at: number; f: () => void }[] = [];
  const read = vi.fn();
  const reader = createErrorReader(read, {
    now: () => t,
    setTimer: (f, ms) => {
      const x = { at: t + ms, f };
      timers.push(x);
      return x;
    },
    clearTimer: (x) => {
      const i = timers.indexOf(x as (typeof timers)[number]);
      if (i >= 0) timers.splice(i, 1);
    },
  });
  const avance = (ms: number) => {
    t += ms;
    timers.filter((x) => x.at <= t).forEach((x) => (timers.splice(timers.indexOf(x), 1), x.f()));
  };
  return { reader, read, avance };
}

describe('lecture automatique des erreurs', () => {
  it('transmet la clé de l’enregistrement avec le texte', () => {
    const { reader, read, avance } = lecteur();
    reader.add('Hakkiil jam', 'k1234abcd');
    avance(BATCH_MS);
    expect(read).toHaveBeenCalledWith([{ text: 'Hakkiil jam', key: 'k1234abcd' }]);
  });

  it('lit à la suite des erreurs affichées ensemble, sans les interrompre', () => {
    const { reader, read, avance } = lecteur();
    reader.add('Première', 'ka');
    avance(100);
    reader.add('Seconde', 'kb');
    avance(BATCH_MS);
    expect(read).toHaveBeenCalledTimes(1);
    expect(read.mock.calls[0][0].map((p: { key: string }) => p.key)).toEqual(['ka', 'kb']);
  });

  it('ne relit pas la même erreur en boucle, mais la relit plus tard', () => {
    const { reader, read, avance } = lecteur();
    reader.add('Erreur', 'ka');
    avance(BATCH_MS);
    reader.add('Erreur', 'ka');
    avance(BATCH_MS);
    expect(read).toHaveBeenCalledTimes(1);
    avance(REPEAT_MS);
    reader.add('Erreur', 'ka');
    avance(BATCH_MS);
    expect(read).toHaveBeenCalledTimes(2);
  });

  it('annuler vide la file', () => {
    const { reader, read, avance } = lecteur();
    reader.add('Erreur', 'ka');
    reader.cancel();
    avance(BATCH_MS * 3);
    expect(read).not.toHaveBeenCalled();
  });

  it('la langue lue suit la page : fulfulde vers la langue de retour, sinon fulfulde', () => {
    expect(readLangFor('fr', { returnLang: 'en' })).toBe('ff');
    expect(readLangFor('ff', { returnLang: 'en' })).toBe('en');
  });
});

describe('réglage « lecture automatique des erreurs »', () => {
  it('est actif par défaut', () => {
    expect(DEFAULT_SETTINGS.autoReadWarnings).toBe(true);
    expect(normalizeSettings(undefined).autoReadWarnings).toBe(true);
  });

  it('passe de la version 1 (éteint par défaut) à la version 2 : actif', () => {
    expect(normalizeSettings({ version: 1, autoReadWarnings: false }).autoReadWarnings).toBe(true);
  });

  it('respecte le choix fait depuis la version 2', () => {
    expect(normalizeSettings({ version: 2, autoReadWarnings: false }).autoReadWarnings).toBe(false);
  });
});
