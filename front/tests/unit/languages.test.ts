import { describe, expect, it } from 'vitest';
import fr from '../../src/locales/fr.json';
import en from '../../src/locales/en.json';
import { LANGUAGES, TARGET } from '../../src/languages';
import { detectLanguage } from '../../src/content/lang';

describe('langue cible', () => {
  it('chaque langue déclarée est complète (code, noms, lettres, variété, textes du panneau)', () => {
    for (const [key, l] of Object.entries(LANGUAGES)) {
      expect(l.code).toBe(key);
      expect(l.name.fr && l.name.en && l.htmlLang.length && l.defaultVariety).toBeTruthy();
      expect(l.letters.flags).toContain('g'); // match() compte les lettres
    }
    for (const dict of [fr, en]) {
      expect(dict.translate.target).toBeTruthy();
      expect(Object.keys(dict.translate.varieties)).toContain(TARGET.defaultVariety);
    }
  });

  it('reconnaît une page dans la langue cible par ses lettres propres, sans vocabulaire codé', () => {
    const letters = (TARGET.letters.source.match(/[^\[\]\\]/g) ?? []).slice(0, 3).join('');
    expect(detectLanguage(`a${letters[0]}a e${letters[1]}e o${letters[2]}o`)).toBe(TARGET.code);
  });
});
