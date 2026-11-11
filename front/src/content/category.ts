/** Indice de catégorie par segment. Simple indice : le serveur décide. */
import type { CategoryHint } from '../services/api';
import type { Container } from './segment';

const SECURITY_RE =
  /(ne\s+(communiquez|partagez|donnez|divulguez|transmettez)|jamais\s+(votre|vos|ton|tes)|code\s+(secret|pin|confidentiel)|\bpin\b|\botp\b|mot\s+de\s+passe|fraud|arnaque|escroqu|hameçonnage|phishing|never\s+share|do\s+not\s+share|don['’]t\s+share|password|scam|sécurité|security|vigilan|méfiez|beware)/i;
const ERROR_RE =
  /(erreur|échec|échoué|invalide|incorrect|insuffisant|impossible|refusé|rejeté|expiré|introuvable|\berror\b|failed|invalid|insufficient|declined|rejected|expired|not\s+found|unable)/i;
const FEES_RE = /(frais|commission|taxe|tarif|coût|\bfees?\b|\bcharges?\b|\bcost\b|\bpricing\b)/i;
const LABEL_TAGS = new Set(['BUTTON', 'LABEL', 'TH', 'DT', 'LEGEND', 'SUMMARY', 'OPTION', 'CAPTION']);

function classAndRole(el: Element | null): { alert: boolean; error: boolean; warning: boolean } {
  const r = { alert: false, error: false, warning: false };
  let cur: Element | null = el;
  for (let depth = 0; cur && depth < 6; depth++, cur = cur.parentElement) {
    const role = cur.getAttribute('role');
    const live = cur.getAttribute('aria-live');
    const cls = (typeof cur.className === 'string' ? cur.className : cur.getAttribute('class') ?? '').toLowerCase();
    if (role === 'alert' || role === 'alertdialog' || live === 'assertive' || live === 'polite' || role === 'status') r.alert = true;
    if (/error|danger|invalid|fail/.test(cls)) r.error = true;
    if (/warn|alert|caution|notice/.test(cls)) r.warning = true;
  }
  return r;
}

export function categorize(parent: Container, text: string, attr?: string): CategoryHint {
  const el = parent.nodeType === 1 ? (parent as Element) : ((parent as ShadowRoot).host ?? null);
  const ctx = classAndRole(el);
  if (SECURITY_RE.test(text)) return 'security_warning';
  if (ctx.error || (ctx.alert && ERROR_RE.test(text))) return 'error';
  if (ERROR_RE.test(text) && (ctx.alert || ctx.warning)) return 'error';
  if (ERROR_RE.test(text) && text.split(/\s+/).length <= 14) return 'error';
  if (FEES_RE.test(text)) return 'fees';
  if (attr) return 'label';
  const tag = el?.tagName ?? '';
  if (LABEL_TAGS.has(tag) || el?.closest('button, label, th, dt, nav, [role=button], [role=tab], [role=menuitem]')) return 'label';
  if (/^H[1-6]$/.test(tag)) return 'label';
  if (text.split(/\s+/).length <= 4 && !/[.!?]$/.test(text.trim())) return 'label';
  return 'instruction';
}
