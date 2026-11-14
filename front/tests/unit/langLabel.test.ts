import { describe, expect, it } from 'vitest';
import { TARGET } from '../../src/languages';
import { makeT } from '../../src/panel/i18n';
import { langLabel } from '../../src/panel/langLabel';

describe('nom des langues dans le panneau', () => {
  for (const ui of ['fr', 'en'] as const) {
    it(`affiche un vrai nom, jamais une clé de traduction (panneau ${ui})`, () => {
      const t = makeT(ui);
      for (const code of ['fr', 'en', TARGET.code]) {
        const label = langLabel(t, code);
        expect(label).not.toMatch(/^translate\./);
        expect(label.length).toBeGreaterThan(1);
      }
      expect(langLabel(t, TARGET.code)).toBe(t('translate.target'));
    });
  }
});
