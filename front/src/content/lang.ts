/**
 * Détection automatique de la langue d'une page ou d'un texte : français, anglais ou la langue cible (voir languages.ts).
 * 1. Attribut lang de la page, 2. lettres propres à la langue cible — aucun vocabulaire
 *    de cette langue n'est codé ici (à fournir par un locuteur natif),
 * 3. mots outils les plus fréquents en français et en anglais.
 */
import { TARGET, type PageLang } from '../languages';

export type { PageLang };

const FR = new Set('le la les de des du un une et est pour par avec sur dans votre vos nous vous ce cette qui que pas au aux en ne plus son sa ses être ou mais'.split(' '));
const EN = new Set('the of and to in is for with on your you this that are be by from at or not as it an have will our we can'.split(' '));

export function detectLanguage(text: string): PageLang | null {
  const sample = text.slice(0, 20000);
  const words = sample.toLowerCase().match(/[\p{L}'’]+/gu) ?? [];
  if (words.length < 2) return null;
  const ffLetters = (sample.match(TARGET.letters) ?? []).length;
  let fr = 0, en = 0;
  for (const w of words) {
    if (FR.has(w)) fr++;
    if (EN.has(w)) en++;
  }
  // les lettres propres à la langue cible sont un signal très fort
  if (ffLetters >= 3 || ffLetters / words.length > 0.01) return TARGET.code;
  if (fr === 0 && en === 0) return null;
  return fr >= en ? 'fr' : 'en';
}

export function detectPageLanguage(doc: Document): PageLang {
  const attr = (doc.documentElement.getAttribute('lang') || '').toLowerCase();
  const fromText = detectLanguage(doc.body?.innerText || doc.body?.textContent || '');
  if (TARGET.htmlLang.some((p) => attr.startsWith(p))) return TARGET.code;
  // le texte l'emporte sur l'attribut : beaucoup de sites gardent lang="en" par défaut
  if (fromText) return fromText;
  if (attr.startsWith('fr')) return 'fr';
  if (attr.startsWith('en')) return 'en';
  return 'fr';
}
