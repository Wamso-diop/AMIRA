/**
 * LANGUE CIBLE de cette version de l'extension : le seul fichier du front à modifier pour en ajouter une.
 * Choisie à la construction : `VITE_AMIRA_LANGUAGE=xx npm run build` (défaut : ff). Mode d'emploi : ../../backend/languages/README.md
 * Aucun mot de la langue n'est écrit ici : seulement ses lettres propres (détection de la page) et ses noms.
 */
export interface TargetLanguage {
  /** Code envoyé à l'API : le même que le dossier backend/languages/<code>/. */
  code: string;
  /** Nom affiché dans le panneau, selon la langue du panneau (fr/en). */
  name: { fr: string; en: string };
  /** Préfixes de l'attribut <html lang> qui annoncent cette langue. */
  htmlLang: string[];
  /** Lettres que n'ont ni le français ni l'anglais : 3 d'entre elles suffisent à reconnaître une page. */
  letters: RegExp;
  /** Variété demandée au serveur (la première de language.json). */
  defaultVariety: string;
}

export const LANGUAGES: Record<string, TargetLanguage> = {
  ff: {
    code: 'ff',
    name: { fr: 'fulfulde', en: 'Fulfulde' },
    htmlLang: ['ff', 'fuv', 'fub'],
    letters: /[ɓƁɗƊƴƳŋŊ]/gu,
    defaultVariety: 'ngaoundere',
  },
  // Exemple à copier : bbj: { code: 'bbj', name: { fr: 'ghomálá’', en: 'Ghomálá’' }, htmlLang: ['bbj'], letters: /[ɛɔɨʉ]/gu, defaultVariety: 'standard' },
};

const wanted = (import.meta.env.VITE_AMIRA_LANGUAGE as string | undefined)?.trim() || 'ff';
export const TARGET: TargetLanguage = LANGUAGES[wanted] ?? LANGUAGES.ff;

/** Un code de langue de page : 'fr', 'en' ou le code de la langue cible. */
export type PageLang = string;
export const isTarget = (lang: string | null | undefined) => lang === TARGET.code;
