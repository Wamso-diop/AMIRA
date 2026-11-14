import { isTarget } from '../languages';
import type { T } from './i18n';

/** Nom affiché d'une langue de traduction : « Français », « English », ou la langue cible (clé `translate.target`). */
export const langLabel = (t: T, code: string): string => t(isTarget(code) ? 'translate.target' : `translate.${code}`);
