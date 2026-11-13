import { describe, expect, it } from 'vitest';
import { harvestNames, hasTranslatableText, mask, maskAroundMarkers, unmask } from '../../src/content/mask';

const sensitive = (text: string, opts = {}) => {
  const r = mask(text, opts);
  return { ...r, leaked: [...r.values.values()].filter((v) => r.text.includes(v)) };
};

describe('mot en minuscules après « à », « pour », « to »', () => {
  // un nom commence par une majuscule : ces mots sont du texte à traduire, pas des noms
  it.each([
    'Total à débiter',
    'Solde insuffisant pour effectuer ce transfert.',
    'Back to hackathon',
    'Total to debit',
    'Merci pour votre confiance',
  ])('%s reste intact', (text) => {
    const r = mask(text, {});
    expect(r.text).toBe(text);
    expect(r.values.size).toBe(0);
  });
});

describe('masquage local', () => {
  it.each([
    ['Votre solde est de 125 000 FCFA.', ['125 000 FCFA']],
    ['Frais : 1 500 F CFA (1,5 %)', ['1 500 F CFA', '1,5 %']],
    ['Montant : XAF 25.000', ['XAF 25.000']],
    ['Total 12,50 €', ['12,50 €']],
    ['Appelez le +237 6 90 12 34 56 ou le 690 12 34 56', ['+237 6 90 12 34 56', '690 12 34 56']],
    ['Écrivez à jean.mbarga@example.cm', ['jean.mbarga@example.cm']],
    ['Opération du 12/03/2025 à 14h30', ['12/03/2025', '14h30']],
    ['Le 3 mars 2025, transfert effectué', ['3 mars 2025']],
    ['Référence : TRX-2025-000123', ['TRX-2025-000123']],
    ['Code de transaction AB12CD34', ['AB12CD34']],
    ['Bénéficiaire : Jean Mbarga', ['Jean Mbarga']],
    ['Envoyer à Mbarga maintenant', ['Mbarga']],
    ['Transfert vers M. Ndjock confirmé', ['M. Ndjock']],
    ['Titulaire : ADAMOU Bello', ['ADAMOU Bello']],
    ['Bonjour, Amina', ['Amina']],
    ['Numéro de compte : CM 001 2345 6789 01', ['001 2345 6789 01']],
  ])('%s', (text, expected) => {
    const r = sensitive(text);
    for (const v of expected) expect([...r.values.values()]).toContain(v);
    for (const v of expected) expect(r.text).not.toContain(v);
    expect(r.text).not.toMatch(/\d/u.test(r.text.replace(/\{N\d+\}/g, '')) ? /.^/ : /.^/);
    expect(r.text.replace(/\{N\d+\}/g, '')).not.toMatch(/\d/);
  });

  it('ne masque pas les mots d’interface', () => {
    const r = mask('Confirmer le transfert');
    expect(r.placeholders).toHaveLength(0);
    expect(mask('Entrez votre code PIN').placeholders).toHaveLength(0);
    expect(mask('Votre Solde').placeholders).toHaveLength(0);
  });

  it('masque les noms de la liste configurable', () => {
    const r = mask('Payer amina pour le loyer', { names: ['Amina'] });
    expect(r.text).toBe('Payer {N0} pour le loyer');
  });

  it('aller-retour : unmask restitue exactement le texte', () => {
    const text = 'Vous envoyez 50 000 FCFA à Jean Mbarga (+237 699 00 11 22) le 01/02/2025.';
    const r = mask(text);
    expect(unmask(r.text, r.values)).toBe(text);
    expect(r.placeholders).toEqual([...r.text.matchAll(/\{N\d+\}/g)].map((m) => m[0]));
  });

  it('masque le texte qui imite un marqueur', () => {
    const r = mask('Valeur {N0} et {B1}');
    expect([...r.values.values()]).toEqual(['{N0}', '{B1}']);
  });

  it('numérotation unique autour des repères de balises', () => {
    const r = maskAroundMarkers('Solde {B0}25 000 FCFA{/B0} au 12/03/2025');
    expect(r.text).toBe('Solde {B0}{N0}{/B0} au {N1}');
    expect(unmask(r.text, r.values)).toBe('Solde {B0}25 000 FCFA{/B0} au 12/03/2025');
  });

  it('apprend les noms complets pour masquer un prénom isolé', () => {
    expect(harvestNames('Amina Ngo Bell')).toEqual(['Amina', 'Ngo', 'Bell']);
    expect(harvestNames('Transfert vers M. Ndjock')).toEqual(['Ndjock']);
    expect(mask('Merci de votre confiance Amina', { names: harvestNames('Amina Ngo Bell') }).text).toBe('Merci de votre confiance {N0}');
  });

  it('ne traduit pas les initiales et sigles courts seuls', () => {
    expect(hasTranslatableText('AN')).toBe(false);
    expect(hasTranslatableText('EN')).toBe(false);
    expect(hasTranslatableText(mask('CM 001 2345 6789 01').text)).toBe(false);
    expect(hasTranslatableText('Valider')).toBe(true);
    expect(hasTranslatableText('SOLDE DISPONIBLE')).toBe(true);
  });

  it('détecte l’absence de texte à traduire', () => {
    expect(hasTranslatableText(mask('125 000 FCFA').text)).toBe(false);
    expect(hasTranslatableText(mask('Solde : 125 000 FCFA').text)).toBe(true);
  });
});

import { detectLanguage } from '../../src/content/lang';
describe('détection de langue', () => {
  it('reconnaît le français, l’anglais et le fulfulde', () => {
    expect(detectLanguage('Votre solde est de 25 000 FCFA. Les frais sont appliqués sur chaque transfert.')).toBe('fr');
    expect(detectLanguage('Your balance is available. The fees are applied to each transfer you make.')).toBe('en');
    // chaîne artificielle : seules les lettres propres au fulfulde comptent
    expect(detectLanguage('aɓa eɗe oŋo uƴu iɓi')).toBe('ff');
  });
});
