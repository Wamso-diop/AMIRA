import { createContext, useContext } from 'react';
import fr from '../locales/fr.json';
import en from '../locales/en.json';

export type UiLang = 'fr' | 'en';
const dicts: Record<UiLang, unknown> = { fr, en };

export type T = (key: string, vars?: Record<string, string | number>) => string;

function lookup(dict: unknown, key: string): unknown {
  return key.split('.').reduce<unknown>((o, k) => (o && typeof o === 'object' ? (o as Record<string, unknown>)[k] : undefined), dict);
}

export function makeT(lang: UiLang): T {
  return (key, vars) => {
    let v = lookup(dicts[lang], key) ?? lookup(dicts.fr, key);
    if (typeof v !== 'string') return key;
    if (vars) for (const [k, val] of Object.entries(vars)) v = (v as string).replace(`{${k}}`, String(val));
    return v as string;
  };
}

/** Listes (ex. confidentialité). */
export function list(lang: UiLang, key: string): string[] {
  const v = lookup(dicts[lang], key) ?? lookup(dicts.fr, key);
  return Array.isArray(v) ? (v as string[]) : [];
}

export const I18n = createContext<{ t: T; lang: UiLang }>({ t: makeT('fr'), lang: 'fr' });
export const useT = () => useContext(I18n);
