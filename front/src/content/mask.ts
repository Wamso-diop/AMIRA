/**
 * Masquage LOCAL avant tout envoi : montants, devises, nombres, téléphones, e-mails, dates,
 * références et noms propres deviennent {N0}, {N1}… La valeur réelle reste en mémoire locale.
 */

export interface MaskResult {
  /** Texte envoyable : plus aucune valeur sensible. */
  text: string;
  /** Marqueur → valeur réelle. Ne quitte jamais le navigateur. */
  values: Map<string, string>;
  /** Marqueurs {N…} créés, dans l'ordre. */
  placeholders: string[];
}

export interface MaskOptions {
  /** Noms propres à toujours masquer (liste configurable). */
  names?: string[];
}

/** Tout marqueur Amira : {N0} (valeur masquée), {B0}/{/B0} (balise interne), {E0} (élément atomique). */
export const MARKER_RE = /\{\/?[NBE]\d+\}/g;

const MONTHS =
  'janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre|' +
  'january|february|march|april|may|june|july|august|september|october|november|december|' +
  'janv\\.?|févr\\.?|fév\\.?|avr\\.?|juil\\.?|sept\\.?|oct\\.?|nov\\.?|déc\\.?|jan\\.?|feb\\.?|mar\\.?|apr\\.?|jun\\.?|jul\\.?|aug\\.?|sep\\.?|dec\\.?';

const SEP = '[\\s\\u00A0\\u202F]';
const NUM = `\\d{1,3}(?:[\\s\\u00A0\\u202F.,']\\d{3})+(?:[.,]\\d+)?|\\d+(?:[.,]\\d+)?`;
const CUR = `F${SEP}?CFA|FCFA|XAF|XOF|CFA|EUR|USD|GBP|NGN|euros?|dollars?|francs?|€|\\$|£|F(?![\\p{L}])`;

const NAME_WORD = "\\p{Lu}[\\p{Ll}\\p{Lu}'’-]*";
const HONORIFIC = 'M\\.|MM\\.|Mme|Mlle|Monsieur|Madame|Mademoiselle|Mr\\.?|Mrs\\.?|Ms\\.?|Miss|Dr\\.?|Pr\\.?|Me';

/** Mots capitalisés courants dans les interfaces : ils ne déclenchent pas la détection de nom. */
const STOP_WORDS = new Set(
  (
    'le la les l un une des du de d au aux votre vos mon ma mes ton ta tes son sa ses notre nos leur leurs ce cet cette ces ' +
    'bienvenue bonjour merci attention confirmer annuler valider envoyer retour suivant précédent solde frais montant total ' +
    'transfert transférer paiement payer compte récapitulatif bénéficiaire erreur alerte important ' +
    'the a an your my our their this that welcome hello thank thanks confirm cancel send next back balance fees fee amount ' +
    'transfer payment pay account summary recipient error warning important please veuillez'
  ).split(' '),
);

interface Span {
  start: number;
  end: number;
}

type Rule = (text: string) => Span[];

function regexRule(re: RegExp, group = 0): Rule {
  return (text) => {
    const out: Span[] = [];
    const r = new RegExp(re.source, re.flags.includes('g') ? re.flags : re.flags + 'g');
    let m: RegExpExecArray | null;
    while ((m = r.exec(text))) {
      if (m[0] === '') {
        r.lastIndex++;
        continue;
      }
      const sub = m[group] ?? m[0];
      const start = m.index + (group ? m[0].indexOf(sub) : 0);
      if (sub) out.push({ start, end: start + sub.length });
    }
    return out;
  };
}

/** Suites de 2+ mots capitalisés (« Jean Mbarga », « MBARGA Jean »), en retirant les mots d'interface en tête. */
const capitalizedSequenceRule: Rule = (text) => {
  const out: Span[] = [];
  const re = new RegExp(`(?<![\\p{L}])${NAME_WORD}(?:[ \\u00A0]+${NAME_WORD})+`, 'gu');
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    const words = m[0].split(/[  ]+/);
    let offset = 0;
    while (words.length && STOP_WORDS.has(words[0].toLowerCase().replace(/['’]$/, ''))) {
      offset += words[0].length;
      words.shift();
      const rest = m[0].slice(offset);
      offset += rest.length - rest.trimStart().length;
    }
    // un mot tout en majuscules de 2-4 lettres seul avec un autre (ex. « CODE PIN ») reste un terme d'interface
    if (words.length >= 2 && !words.every((w) => /^\p{Lu}{2,5}$/u.test(w))) {
      out.push({ start: m.index + offset, end: m.index + m[0].length });
    }
  }
  return out;
};

/** Mot capitalisé isolé après « à », « pour », « bénéficiaire : »… (« Envoyer à Mbarga »). */
const contextualNameRule: Rule = (text) => {
  const out: Span[] = [];
  const re = new RegExp(
    `(?:(?<![\\p{L}])(?:à|pour|vers|chez|de la part de|to|for|from|by|bonjour|bonsoir|salut|bienvenue|merci|cher|chère|hello|hi|welcome|dear|thanks)(?:${SEP}*,)?|(?:nom|name|bénéficiaire|beneficiary|recipient|destinataire|titulaire|holder|client|customer)${SEP}*:)${SEP}+(${NAME_WORD})`,
    'giu',
  );
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    const word = m[1];
    // le drapeau « i » (pour « À ») fait aussi accepter une minuscule : « à débiter » n'est pas un nom
    if (word[0] === word[0].toLowerCase() || STOP_WORDS.has(word.toLowerCase())) continue;
    const start = m.index + m[0].length - word.length;
    out.push({ start, end: start + word.length });
  }
  return out;
};

function nameListRule(names: string[]): Rule {
  const clean = names.map((n) => n.trim()).filter((n) => n.length >= 2);
  if (!clean.length) return () => [];
  const esc = clean.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).sort((a, b) => b.length - a.length);
  return regexRule(new RegExp(`(?<![\\p{L}])(?:${esc.join('|')})(?![\\p{L}])`, 'giu'));
}

/** Règles par priorité : la première qui couvre une zone l'emporte. */
function rules(opts: MaskOptions): Rule[] {
  return [
    // texte qui ressemble déjà à un marqueur : masqué pour ne pas fausser la vérification
    regexRule(/\{\/?[A-Z]\d+\}/g),
    regexRule(/[\p{L}\d._%+-]+@[\p{L}\d-]+(?:\.[\p{L}\d-]+)+/gu),
    regexRule(/\b(?:https?:\/\/|www\.)[^\s<>"']+/gi),
    nameListRule(opts.names ?? []),
    // références : codes mêlant lettres et chiffres, avec ou sans séparateurs
    regexRule(/\b(?=[A-Z0-9_/#-]*\d)(?=[A-Z0-9_/#-]*[A-Z])[A-Z0-9]+(?:[-_/#][A-Z0-9]+)+\b/g),
    regexRule(/\b(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{5,}\b/g),
    regexRule(/#\d+/g),
    // IBAN / RIB
    regexRule(/\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,8}(?:[ ]?[A-Z0-9]{1,4})?\b/g),
    // téléphones : international et formats camerounais (6XX XX XX XX, 2XX XX XX XX)
    regexRule(new RegExp(`(?:\\+|00)\\d{1,3}(?:${SEP}|[.-])?\\(?\\d\\)?(?:(?:${SEP}|[.-])?\\d){6,12}`, 'g')),
    regexRule(new RegExp(`\\b[62]\\d{2}(?:(?:${SEP}|[.-])?\\d{2}){3}\\b`, 'g')),
    // dates et heures
    regexRule(/\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b/g),
    regexRule(/\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?\b/g),
    regexRule(new RegExp(`\\b\\d{1,2}(?:er|st|nd|rd|th)?${SEP}+(?:${MONTHS})(?:${SEP}+\\d{2,4})?(?![\\p{L}])`, 'giu')),
    regexRule(new RegExp(`(?<![\\p{L}])(?:${MONTHS})${SEP}+\\d{1,2}(?:,?${SEP}+\\d{4})?\\b`, 'giu')),
    regexRule(/\b\d{1,2}(?:[:h]\d{2})(?::\d{2})?\b/gi),
    // montants avec devise (avant ou après), pourcentages
    regexRule(new RegExp(`(?:(?:${CUR})${SEP}?)?(?:${NUM})${SEP}?(?:${CUR})`, 'gu')),
    regexRule(new RegExp(`(?:${CUR})${SEP}?(?:${NUM})`, 'gu')),
    regexRule(new RegExp(`(?:${NUM})${SEP}?%`, 'g')),
    // devise seule
    regexRule(/(?<![\p{L}])(?:F[\s ]?CFA|FCFA|XAF|XOF|EUR|USD|GBP|NGN)(?![\p{L}])|[€$£]/gu),
    // tout autre nombre
    regexRule(new RegExp(NUM, 'g')),
    // noms propres
    regexRule(new RegExp(`(?:${HONORIFIC})${SEP}+${NAME_WORD}(?:${SEP}+${NAME_WORD})*`, 'gu')),
    capitalizedSequenceRule,
    contextualNameRule,
  ];
}

export function mask(text: string, opts: MaskOptions = {}): MaskResult {
  const accepted: Span[] = [];
  for (const rule of rules(opts)) {
    for (const span of rule(text)) {
      if (accepted.some((a) => span.start < a.end && a.start < span.end)) continue;
      accepted.push(span);
    }
  }
  accepted.sort((a, b) => a.start - b.start);
  const values = new Map<string, string>();
  const placeholders: string[] = [];
  let out = '';
  let pos = 0;
  accepted.forEach((span, i) => {
    const token = `{N${i}}`;
    out += text.slice(pos, span.start) + token;
    values.set(token, text.slice(span.start, span.end));
    placeholders.push(token);
    pos = span.end;
  });
  out += text.slice(pos);
  return { text: out, values, placeholders };
}

/** Remet les valeurs réelles, localement, après réception de la traduction. */
export function unmask(text: string, values: Map<string, string>): string {
  return text.replace(/\{N\d+\}/g, (t) => values.get(t) ?? t);
}

/** Masquage d'un texte qui contient déjà des marqueurs de balises {B0}… : on ne masque qu'entre eux. */
export function maskAroundMarkers(text: string, opts: MaskOptions = {}): MaskResult {
  const parts = text.split(/(\{\/?[BE]\d+\})/g);
  const values = new Map<string, string>();
  const placeholders: string[] = [];
  let n = 0;
  const out = parts
    .map((part, i) => {
      if (i % 2 === 1) return part;
      const r = mask(part, opts);
      // renumérote pour que les marqueurs soient uniques dans tout le segment
      return r.text.replace(/\{N(\d+)\}/g, (tok) => {
        const nt = `{N${n++}}`;
        values.set(nt, r.values.get(tok)!);
        placeholders.push(nt);
        return nt;
      });
    })
    .join('');
  return { text: out, values, placeholders };
}

/**
 * Indique s'il reste quelque chose à traduire : un mot avec une minuscule, ou un mot de 4 lettres
 * ou plus. Les initiales et sigles courts seuls (« AN », « EN », « CM ») ne sont pas envoyés.
 */
export function hasTranslatableText(masked: string): boolean {
  const words = masked.replace(MARKER_RE, ' ').match(/\p{L}+/gu) ?? [];
  return words.some((w) => (w.length >= 2 && /\p{Ll}/u.test(w)) || w.length >= 4);
}

/**
 * Noms propres repérés avec certitude (suite de mots capitalisés, civilité) : leurs mots servent
 * ensuite à masquer le même nom quand il apparaît seul ailleurs (« Bonjour, Amina »).
 */
export function harvestNames(text: string): string[] {
  const out: string[] = [];
  const spans = [
    ...capitalizedSequenceRule(text),
    ...regexRule(new RegExp(`(?:${HONORIFIC})${SEP}+(${NAME_WORD}(?:${SEP}+${NAME_WORD})*)`, 'gu'), 1)(text),
  ];
  for (const sp of spans) {
    for (const w of text.slice(sp.start, sp.end).split(/[\s\u00A0]+/)) {
      const clean = w.replace(/[.,;:]+$/, '');
      if (clean.length >= 3 && !STOP_WORDS.has(clean.toLowerCase()) && !/^(?:M|MM|Mme|Mlle|Monsieur|Madame|Mademoiselle|Mr|Mrs|Ms|Miss|Dr|Pr|Me)\.?$/.test(clean)) out.push(clean);
    }
  }
  return out;
}
