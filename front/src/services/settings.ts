import { TARGET } from '../languages';
import type { Variety } from './api';
import type { MockScenario } from './mock';

export type DisplayMode = 'replace' | 'bilingual' | 'hover';
export type Theme = 'light' | 'dark' | 'system';

export interface Settings {
  version: 2;
  onboarded: boolean;
  /** Langue d'arrivée quand la page est dans la langue cible (sinon on traduit toujours vers la langue cible). */
  returnLang: 'fr' | 'en';
  variety: Variety;
  display: DisplayMode;
  // Sécurité
  prudence: boolean;
  confidenceThreshold: number;
  /** Toujours vrai : le masquage local n'est pas désactivable. */
  readonly maskSensitive: true;
  /** Noms propres à toujours masquer (liste configurable). */
  extraNames: string[];
  // Voix
  ttsSpeed: number;
  /** Lit à voix haute, dès qu'il s'affiche, un message d'erreur de la page (actif par défaut). */
  autoReadWarnings: boolean;
  // Accessibilité
  textScale: number;
  highContrast: boolean;
  theme: Theme;
  reduceMotion: boolean;
  uiLanguage: 'fr' | 'en';
  // Interne
  /** Scénario de la simulation (tests et démonstration ; pas d'interface). */
  mockScenario: MockScenario;
  enabledSites: string[];
  /** Autorisation accordée pour tous les sites web (Amira reste inactif tant qu'on ne l'active pas). */
  allSites: boolean;
}

export const DEFAULT_SETTINGS: Settings = {
  version: 2,
  onboarded: false,
  returnLang: 'fr',
  variety: TARGET.defaultVariety,
  display: 'replace',
  prudence: true,
  confidenceThreshold: 0.7,
  maskSensitive: true,
  extraNames: [],
  ttsSpeed: 1,
  autoReadWarnings: true,
  textScale: 1,
  highContrast: false,
  theme: 'system',
  reduceMotion: false,
  uiLanguage: 'fr',
  mockScenario: 'normal',
  enabledSites: ['https://safinum.cm/*'],
  allSites: false,
};

export const SETTINGS_KEY = 'amira.settings';

export function normalizeSettings(raw: unknown): Settings {
  const r = (raw && typeof raw === 'object' ? raw : {}) as Partial<Settings>;
  // version 1 : lecture automatique éteinte par défaut ; depuis la version 2 elle est active par défaut
  const from = r.version === 2 ? r : { ...r, autoReadWarnings: true };
  return { ...DEFAULT_SETTINGS, ...from, maskSensitive: true, version: 2 };
}

export async function loadSettings(): Promise<Settings> {
  const got = await chrome.storage.local.get(SETTINGS_KEY);
  return normalizeSettings(got[SETTINGS_KEY]);
}

export async function saveSettings(patch: Partial<Settings>): Promise<Settings> {
  const next = normalizeSettings({ ...(await loadSettings()), ...patch });
  await chrome.storage.local.set({ [SETTINGS_KEY]: next });
  return next;
}
