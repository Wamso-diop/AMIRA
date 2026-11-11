/**
 * Segmentation du texte visible par BLOCS, indépendante du site.
 * Une phrase découpée en <b>, <a>, <span>… forme UN segment ; les balises internes deviennent
 * des repères {B0}…{/B0}, les éléments atomiques (champ, image, saut de ligne) des repères {E0}.
 */

const INLINE_TAGS = new Set([
  'A', 'ABBR', 'B', 'BDI', 'BDO', 'CITE', 'DATA', 'DFN', 'EM', 'I', 'MARK', 'Q', 'S', 'SMALL', 'SPAN', 'STRONG',
  'SUB', 'SUP', 'TIME', 'U', 'VAR', 'FONT', 'LABEL', 'DEL', 'INS', 'NOBR', 'BIG', 'TT',
]);

/** Éléments gardés tels quels dans la phrase, sans toucher à leur contenu. */
const ATOMIC_TAGS = new Set([
  'BR', 'WBR', 'IMG', 'SVG', 'CANVAS', 'VIDEO', 'AUDIO', 'IFRAME', 'INPUT', 'SELECT', 'TEXTAREA', 'OBJECT', 'EMBED',
  'MATH', 'CODE', 'KBD', 'SAMP', 'PRE', 'PICTURE', 'METER', 'PROGRESS', 'OUTPUT',
]);

/** Jamais lus. */
const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'META', 'LINK', 'HEAD', 'TITLE', 'OPTION', 'DATALIST']);

/** Attributs traduits (texte d'interface, jamais des valeurs saisies). */
export const TRANSLATABLE_ATTRS = ['placeholder', 'aria-label', 'title'] as const;

export const UI_ATTR = 'data-amira-ui';

export function isIgnored(el: Element): boolean {
  if (SKIP_TAGS.has(el.tagName)) return true;
  if (el.hasAttribute(UI_ATTR)) return true;
  if (el.closest('[data-amira-ignore]')) return true;
  if ((el as HTMLElement).isContentEditable) return true;
  if (el.hasAttribute('hidden')) return true;
  return false;
}

function isHiddenByStyle(el: Element): boolean {
  const view = el.ownerDocument?.defaultView;
  if (!view) return false;
  const cs = view.getComputedStyle(el);
  return cs.display === 'none' || cs.visibility === 'hidden';
}

export function isAtomic(el: Element): boolean {
  return ATOMIC_TAGS.has(el.tagName) || el.namespaceURI === 'http://www.w3.org/2000/svg';
}

/** Élément « en ligne » qui peut faire partie d'une phrase (sans bloc à l'intérieur). */
export function isInlineFlow(el: Element, memo: WeakMap<Element, boolean>): boolean {
  const known = memo.get(el);
  if (known !== undefined) return known;
  let result = false;
  if (INLINE_TAGS.has(el.tagName) && !el.shadowRoot) {
    const view = el.ownerDocument?.defaultView;
    const display = view ? view.getComputedStyle(el).display : 'inline';
    if (display === 'inline' || display === '' || display === 'contents') {
      result = true;
      for (const child of Array.from(el.children)) {
        if (isIgnored(child)) continue;
        if (!(isAtomic(child) || isInlineFlow(child, memo))) {
          result = false;
          break;
        }
      }
    }
  }
  memo.set(el, result);
  return result;
}

export type Container = Element | ShadowRoot;

/** Un groupe = nœuds frères consécutifs formant une phrase. */
export interface Group {
  parent: Container;
  nodes: Node[];
}

/** Plan de reconstruction d'un segment. */
export interface Serialized {
  /** Texte avec repères, espaces normalisés, sans masquage. */
  text: string;
  /** Repères dans l'ordre d'apparition (squelette). */
  skeleton: string[];
  /** Emplacements de texte entre repères : nœuds texte d'origine. */
  slots: Text[][];
  elements: Map<string, Element>;
  atomics: Map<string, Node>;
  /** Pour chaque élément en ligne, sa liste d'enfants d'origine. */
  childLists: Map<Element, Node[]>;
}

export function serializeGroup(group: Group): Serialized {
  const s: Serialized = { text: '', skeleton: [], slots: [[]], elements: new Map(), atomics: new Map(), childLists: new Map() };
  let b = 0;
  let e = 0;
  const pushMarker = (m: string) => {
    s.text += m;
    s.skeleton.push(m);
    s.slots.push([]);
  };
  const walk = (nodes: Node[]) => {
    for (const node of nodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        s.text += (node as Text).data;
        s.slots[s.slots.length - 1].push(node as Text);
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        const el = node as Element;
        if (isAtomic(el) || isIgnored(el)) {
          const m = `{E${e++}}`;
          s.atomics.set(m, el);
          pushMarker(m);
        } else {
          const id = b++;
          s.elements.set(`B${id}`, el);
          s.childLists.set(el, Array.from(el.childNodes));
          pushMarker(`{B${id}}`);
          walk(Array.from(el.childNodes));
          pushMarker(`{/B${id}}`);
        }
      }
      // commentaires : ignorés
    }
  };
  walk(group.nodes);
  s.text = s.text.replace(/[\s ]+/g, (ws) => (ws.includes(' ') && !/[\n\t]/.test(ws) ? ws : ' ')).trim();
  return s;
}

export interface ScanResult {
  groups: Group[];
  attrs: { el: Element; attr: string; value: string }[];
  shadowRoots: ShadowRoot[];
}

/**
 * Parcourt un conteneur et renvoie les groupes de texte visibles et les attributs traduisibles.
 * Descend dans les shadow DOM ouverts et les iframes de même origine (si `frames`).
 */
export function scan(root: Container, opts: { frames?: boolean; owned?: (n: Node) => boolean } = {}): ScanResult {
  const memo = new WeakMap<Element, boolean>();
  const result: ScanResult = { groups: [], attrs: [], shadowRoots: [] };

  const collectAttrs = (el: Element) => {
    for (const attr of TRANSLATABLE_ATTRS) {
      const v = el.getAttribute(attr);
      if (v && v.trim()) result.attrs.push({ el, attr, value: v });
    }
    // libellé d'un bouton <input type=submit> sans nom (sa valeur n'est alors pas envoyée au serveur du site)
    if (el.tagName === 'INPUT' && /^(submit|button|reset)$/i.test((el as HTMLInputElement).type) && !el.hasAttribute('name')) {
      const v = el.getAttribute('value');
      if (v && v.trim()) result.attrs.push({ el, attr: 'value', value: v });
    }
  };

  const visitContainer = (container: Container) => {
    let current: Node[] = [];
    const flush = () => {
      // retire les espaces et éléments atomiques en bordure
      let start = 0;
      let end = current.length;
      const edge = (n: Node) =>
        (n.nodeType === Node.TEXT_NODE && !(n as Text).data.trim()) ||
        n.nodeType === Node.COMMENT_NODE ||
        (n.nodeType === Node.ELEMENT_NODE && (isAtomic(n as Element) || isIgnored(n as Element)));
      while (start < end && edge(current[start])) start++;
      while (end > start && edge(current[end - 1])) end--;
      let nodes = current.slice(start, end);
      let parent: Container = container;
      // un seul élément en ligne qui porte toute la phrase : on descend dedans (évite des repères inutiles)
      while (nodes.length === 1 && nodes[0].nodeType === Node.ELEMENT_NODE) {
        const only = nodes[0] as Element;
        parent = only;
        const kids = Array.from(only.childNodes);
        let s = 0;
        let en = kids.length;
        while (s < en && edge(kids[s])) s++;
        while (en > s && edge(kids[en - 1])) en--;
        nodes = kids.slice(s, en);
      }
      if (nodes.some((n) => n.nodeType === Node.TEXT_NODE ? /\S/.test((n as Text).data) : /\S/.test(n.textContent ?? ''))) {
        result.groups.push({ parent, nodes });
      }
      current = [];
    };

    for (const child of Array.from(container.childNodes)) {
      if (child.nodeType === Node.TEXT_NODE) {
        current.push(child);
        continue;
      }
      if (child.nodeType !== Node.ELEMENT_NODE) continue;
      const el = child as Element;
      if (isIgnored(el)) {
        flush();
        continue;
      }
      if (isAtomic(el)) {
        collectAttrs(el);
        current.push(el);
        if (opts.frames && el.tagName === 'IFRAME') {
          try {
            const doc = (el as HTMLIFrameElement).contentDocument;
            if (doc?.body) visitContainer(doc.body);
          } catch {
            /* iframe d'une autre origine : traitée par sa propre instance du script */
          }
        }
        continue;
      }
      if (isInlineFlow(el, memo)) {
        if (isHiddenByStyle(el)) continue;
        el.querySelectorAll('*').forEach((d) => collectAttrs(d));
        collectAttrs(el);
        current.push(el);
        continue;
      }
      flush();
      if (isHiddenByStyle(el)) continue;
      collectAttrs(el);
      visitContainer(el);
      if (el.shadowRoot) {
        result.shadowRoots.push(el.shadowRoot);
        visitContainer(el.shadowRoot);
      }
    }
    flush();
  };

  visitContainer(root);
  return result;
}

/** Découpe une traduction masquée en morceaux de texte et repères. */
export function tokenize(text: string): { markers: string[]; pieces: string[] } {
  const parts = text.split(/(\{\/?[BE]\d+\})/g);
  const pieces: string[] = [];
  const markers: string[] = [];
  parts.forEach((p, i) => (i % 2 === 0 ? pieces.push(p) : markers.push(p)));
  return { markers, pieces };
}

export interface Applied {
  /** Nœuds texte écrits par Amira → valeur écrite (sert à ignorer nos propres mutations). */
  written: Map<Text, string>;
  restore: () => void;
}

function leadingWs(s: string) {
  return s.match(/^\s*/)![0];
}
function trailingWs(s: string) {
  return s.match(/\s*$/)![0];
}

/**
 * Applique une traduction (repères déjà vérifiés, valeurs réelles remises) au DOM.
 * Même ordre de repères : écriture sur place dans les nœuds texte existants (compatible avec les
 * frameworks qui gardent des références vers ces nœuds). Ordre différent : reconstruction en
 * déplaçant les éléments d'origine (leurs écouteurs restent attachés).
 */
export function applyTranslation(group: Group, ser: Serialized, translated: string): Applied {
  const { markers, pieces } = tokenize(translated);
  const written = new Map<Text, string>();
  const sameOrder = markers.length === ser.skeleton.length && markers.every((m, i) => m === ser.skeleton[i]);

  if (sameOrder) {
    const originals = new Map<Text, string>();
    const created: Text[] = [];
    const firstSlot = ser.slots.findIndex((s) => s.length);
    const lastSlot = ser.slots.length - 1 - [...ser.slots].reverse().findIndex((s) => s.length);
    ser.slots.forEach((slot, i) => {
      let piece = pieces[i] ?? '';
      if (slot.length) {
        // conserve les espaces de bord d'origine
        const orig = slot.map((t) => t.data).join('');
        if (i === firstSlot) piece = leadingWs(orig) + piece.trimStart();
        if (i === lastSlot) piece = piece.trimEnd() + trailingWs(orig);
        slot.forEach((t, k) => {
          originals.set(t, t.data);
          const v = k === 0 ? piece : '';
          if (t.data !== v) t.data = v;
          written.set(t, v);
        });
      } else if (piece.trim()) {
        // emplacement vide à l'origine : insère un nœud texte au bon endroit
        const node = (group.nodes[0].ownerDocument ?? document).createTextNode(piece);
        const prevMarker = ser.skeleton[i - 1];
        const anchorAfter = prevMarker ? markerNode(ser, prevMarker) : null;
        const opening = prevMarker && /^\{B/.test(prevMarker);
        if (anchorAfter && opening) anchorAfter.insertBefore(node, anchorAfter.firstChild);
        else if (anchorAfter) anchorAfter.parentNode?.insertBefore(node, anchorAfter.nextSibling);
        else group.nodes[0].parentNode?.insertBefore(node, group.nodes[0]);
        created.push(node);
        written.set(node, piece);
      }
    });
    return {
      written,
      restore: () => {
        originals.forEach((v, t) => {
          // ne jamais écraser un texte que le site a réécrit entre-temps
          if (written.get(t) === t.data && t.data !== v) t.data = v;
        });
        created.forEach((t) => t.remove());
      },
    };
  }

  // Reconstruction : on retire les nœuds du groupe et on réinsère dans l'ordre traduit.
  const parent = group.nodes[0].parentNode!;
  const after = group.nodes[group.nodes.length - 1].nextSibling;
  const build = (): Node[] => {
    const root: Node[] = [];
    const stack: { el: Element | null; kids: Node[] }[] = [{ el: null, kids: root }];
    pieces.forEach((piece, i) => {
      if (piece) {
        const t = (group.nodes[0].ownerDocument ?? document).createTextNode(piece);
        written.set(t, piece);
        stack[stack.length - 1].kids.push(t);
      }
      const m = markers[i];
      if (!m) return;
      if (m.startsWith('{E')) stack[stack.length - 1].kids.push(ser.atomics.get(m)!);
      else if (m.startsWith('{/B')) {
        const top = stack.pop()!;
        top.el!.replaceChildren(...top.kids);
      } else {
        const el = ser.elements.get(m.slice(1, -1))!;
        stack[stack.length - 1].kids.push(el);
        stack.push({ el, kids: [] });
      }
    });
    return root;
  };
  const fresh = build();
  group.nodes.forEach((n) => n.parentNode === parent && parent.removeChild(n));
  fresh.forEach((n) => parent.insertBefore(n, after));
  return {
    written,
    restore: () => {
      fresh.forEach((n) => n.parentNode === parent && parent.removeChild(n));
      ser.childLists.forEach((kids, el) => el.replaceChildren(...kids));
      group.nodes.forEach((n) => parent.insertBefore(n, after && after.parentNode === parent ? after : null));
    },
  };
}

function markerNode(ser: Serialized, marker: string): Node | null {
  if (marker.startsWith('{E')) return ser.atomics.get(marker) ?? null;
  const id = marker.replace(/[{}/]/g, '');
  return ser.elements.get(id) ?? null;
}
