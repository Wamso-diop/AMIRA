import type { Variety } from './api';
import type { MockScenario } from './mock';

export type DisplayMode = 'replace' | 'bilingual' | 'hover';
export type Theme = 'light' | 'dark' | 'system';

export interface Settings {
  version: 1;
  onboarded: boolean;
  /** Langue d'arrivée quand la page est en fulfulde (sinon on traduit toujours vers le fulfulde). */
  ffTarget: 'fr' | 'en';
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
  version: 1,
  onboarded: false,
  ffTarget: 'fr',
  variety: 'ngaoundere',
  display: 'replace',
  prudence: true,
  confidenceThreshold: 0.7,
  maskSensitive: true,
  extraNames: [],
  ttsSpeed: 1,
  autoReadWarnings: false,
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
  return { ...DEFAULT_SETTINGS, ...r, maskSensitive: true, version: 1 };
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
