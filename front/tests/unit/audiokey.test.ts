import { describe, expect, it } from 'vitest';
import { audioKey, segmentKey } from '../../src/content/engine';

// mêmes valeurs que backend/tests/test_voice.py (audio_key) : le front et le serveur doivent calculer la même clé
describe('clé de l’enregistrement', () => {
  it.each([
    ['Bonjour, {N0}', 'k53142120'], // fin = nom masqué : l’enregistrement est celui du début
    ['Numéro de compte : CM {N0}', 'k04c754e4'],
    ['Le montant doit être supérieur à {N0}.', 'k52f33b18'],
    ['Bonjour', 'k53142120'], // rien à retirer : clé ordinaire
  ])('%s', (masked, key) => {
    expect(audioKey(masked)).toBe(key);
  });

  it('un texte sans marqueur en fin garde sa clé ordinaire', () => {
    expect(audioKey('Votre {N0} compte')).toBe(segmentKey('Votre {N0} compte'));
  });
});
