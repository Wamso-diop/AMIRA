import { describe, expect, it } from 'vitest';
import { decide, markersMatch, tagsWellNested } from '../../src/content/verify';

const base = { prudence: false, threshold: 0.7 };

describe('vérification des marqueurs', () => {
  it('accepte un ordre différent si l’ensemble est identique', () => {
    expect(markersMatch('Envoyer {N0} à {N1}', '{N1} … {N0}')).toBe(true);
  });
  it('refuse un marqueur perdu, doublé ou inventé', () => {
    expect(markersMatch('{N0} et {N1}', '{N0}')).toBe(false);
    expect(markersMatch('{N0}', '{N0} {N0}')).toBe(false);
    expect(markersMatch('{N0}', '{N0} {N1}')).toBe(false);
    expect(markersMatch('{B0}x{/B0}', '{B0}x')).toBe(false);
  });
  it('vérifie l’imbrication des balises', () => {
    expect(tagsWellNested('{B0}a{B1}b{/B1}{/B0}')).toBe(true);
    expect(tagsWellNested('{B0}a{B1}b{/B0}{/B1}')).toBe(false);
  });
});

describe('décision d’affichage', () => {
  const ok = { text: '⟦FF⟧ {N0}', status: 'machine', confidence: 0.8 };
  it('applique une traduction correcte', () => {
    expect(decide({ ...base, sentMasked: '{N0}', received: ok })).toEqual({ apply: true });
  });
  it('garde l’original si marqueurs différents', () => {
    expect(decide({ ...base, sentMasked: '{N0} {N1}', received: ok })).toEqual({ apply: false, reason: 'markers' });
  });
  it('garde l’original si incertain', () => {
    expect(decide({ ...base, sentMasked: '{N0}', received: { ...ok, status: 'uncertain' } })).toMatchObject({ apply: false, reason: 'uncertain' });
  });
  it('avertissement de sécurité : seulement la version validée', () => {
    expect(decide({ ...base, sentMasked: '{N0}', category: 'security_warning', received: ok })).toMatchObject({ apply: false, reason: 'security' });
    expect(decide({ ...base, sentMasked: '{N0}', category: 'security_warning', received: { ...ok, status: 'validated' } })).toEqual({ apply: true });
  });
  it('mode prudence : seuil de confiance', () => {
    expect(decide({ prudence: true, threshold: 0.9, sentMasked: '{N0}', received: ok })).toMatchObject({ reason: 'threshold' });
    expect(decide({ prudence: true, threshold: 0.7, sentMasked: '{N0}', received: ok })).toEqual({ apply: true });
  });
  it('segment absent de la réponse', () => {
    expect(decide({ ...base, sentMasked: 'x' })).toMatchObject({ reason: 'missing' });
  });
});
