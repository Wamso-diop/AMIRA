/** Vérification des marqueurs : l'ensemble reçu doit être IDENTIQUE à l'ensemble envoyé. */
import { MARKER_RE } from './mask';

export function extractMarkers(text: string): string[] {
  return (text.match(MARKER_RE) ?? []).slice().sort();
}

export function markersMatch(sent: string, received: string): boolean {
  const a = extractMarkers(sent);
  const b = extractMarkers(received);
  return a.length === b.length && a.every((m, i) => m === b[i]);
}

/** Les balises {B0}…{/B0} doivent rester bien imbriquées pour pouvoir reconstruire le DOM. */
export function tagsWellNested(text: string): boolean {
  const stack: string[] = [];
  for (const m of text.match(/\{\/?B\d+\}/g) ?? []) {
    if (m[1] === '/') {
      if (stack.pop() !== m.slice(2, -1)) return false;
    } else stack.push(m.slice(1, -1));
  }
  return stack.length === 0;
}

export type Decision =
  | { apply: true }
  | { apply: false; reason: 'markers' | 'uncertain' | 'threshold' | 'security' | 'missing' | 'nesting' };

export interface DecisionInput {
  sentMasked: string;
  received?: { text: string; status: string; confidence: number };
  category?: string;
  prudence: boolean;
  threshold: number;
}

/** Règle unique de décision : en cas de doute, on garde le texte original. Jamais de remplacement partiel. */
export function decide(i: DecisionInput): Decision {
  if (!i.received || typeof i.received.text !== 'string') return { apply: false, reason: 'missing' };
  if (!markersMatch(i.sentMasked, i.received.text)) return { apply: false, reason: 'markers' };
  if (!tagsWellNested(i.received.text)) return { apply: false, reason: 'nesting' };
  if (i.received.status === 'uncertain') return { apply: false, reason: 'uncertain' };
  // les avertissements de sécurité ne s'affichent que dans leur version validée
  if (i.category === 'security_warning' && i.received.status !== 'validated') return { apply: false, reason: 'security' };
  if (i.prudence && i.received.status !== 'validated' && !(i.received.confidence >= i.threshold)) return { apply: false, reason: 'threshold' };
  return { apply: true };
}
