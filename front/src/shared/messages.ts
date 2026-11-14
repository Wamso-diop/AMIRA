import type {
  Capabilities,
  FeedbackRequest,
  TranslateRequest,
  TranslateResponse,
  TtsRequest,
  TtsResult,
} from '../services/api';
import type { LogEntry } from '../services/log';

/** Messages vers le service worker (panneau ou script de contenu → arrière-plan). */
export type BgRequest =
  | { type: 'amira:translate'; req: TranslateRequest; hote?: string }
  | { type: 'amira:status' }
  | { type: 'amira:tts'; req: TtsRequest }
  | { type: 'amira:stt'; audioBase64: string; mimeType: string; language: string }
  | { type: 'amira:feedback'; req: FeedbackRequest }
  | { type: 'amira:log'; entry: Partial<LogEntry> }
  | { type: 'amira:clearCache' };

export type ServerState = 'ready' | 'busy' | 'offline' | 'notConnected' | 'error';

export interface StatusResult {
  state: ServerState;
  demo: boolean;
  /** L'extension agit seule : mémoire validée et voix embarquées (pas de serveur nécessaire). */
  autonomous?: boolean;
  capabilities: Capabilities | null;
  errorCode?: string;
}

export type BgResult<T> = { ok: true; data: T } | { ok: false; code: string; message: string; retryAfterMs?: number };

export type TranslateResult = BgResult<TranslateResponse & { fromCache: number }>;
export type TtsResultMsg = BgResult<TtsResult>;

/** Commandes du panneau vers le script de contenu de l'onglet actif. */
export type ContentCommand =
  | { type: 'amira:setEnabled'; enabled: boolean }
  | { type: 'amira:showOriginal'; on: boolean }
  | { type: 'amira:getStats' }
  | { type: 'amira:retry' }
  | { type: 'amira:readable'; what: 'page' | 'selection' | 'messages' | 'report' }
  | PickCommand;

/**
 * Sélecteur de passages (onglet Voix, « La sélection ») : la page est déjà découpée en segments ;
 * l'utilisateur choisit des segments entiers, jamais un morceau de phrase. Chaque segment a une clé
 * stable (`key`) qui permet au serveur de renvoyer l'enregistrement d'un locuteur natif.
 */
export type PickCommand =
  | { type: 'amira:pick'; action: 'list' }
  | { type: 'amira:pick'; action: 'start'; selected: string[] }
  | { type: 'amira:pick'; action: 'stop' }
  | { type: 'amira:pick'; action: 'set'; selected: string[] }
  | { type: 'amira:pick'; action: 'focus'; id: string | null; flash?: boolean };

export interface PickItem {
  id: string;
  /** Clé stable du segment (empreinte du texte source masqué) : sert à retrouver l'audio enregistré. */
  key: string;
  /** Texte MASQUÉ à lire (traduction affichée si elle existe). */
  text: string;
  /** Aperçu pour la liste du panneau (reste en local, jamais envoyé). */
  preview: string;
  category?: string;
}

export interface PickState {
  items: PickItem[];
  selected: string[];
  active: boolean;
}

export interface PageStats {
  enabled: boolean;
  showingOriginal: boolean;
  translated: number;
  kept: number;
  errors: number;
  pending: number;
  total: number;
  hote?: string;
  /** Langue de la page détectée automatiquement. */
  lang?: string;
}

/** Texte lisible renvoyé au panneau pour la voix : déjà MASQUÉ. */
export interface Readable {
  segments: { id: string; text: string; category?: string; shown?: string; key?: string }[];
}

/** Notification du script de contenu vers le panneau. */
export type ContentEvent =
  | { type: 'amira:stats'; stats: PageStats }
  /** Message d'erreur affiché sur la page (texte masqué) ; key : clé de l'enregistrement du natif, si elle existe. */
  | { type: 'amira:error'; text: string; key: string }
  | { type: 'amira:picked'; state: PickState };

export const EMPTY_STATS: PageStats = { enabled: false, showingOriginal: false, translated: 0, kept: 0, errors: 0, pending: 0, total: 0 };
