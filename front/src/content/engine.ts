/**
 * Moteur du script de contenu, indépendant de chrome.* (testable avec le mock).
 * Capture → masquage local → envoi → vérification → affichage, et retour instantané à l'original.
 */
import { newRequestId, type CategoryHint, type TranslateRequest, type Variety } from '../services/api';
import { detectLanguage, detectPageLanguage, type PageLang } from './lang';
import type { LogEntry } from '../services/log';
import type { DisplayMode } from '../services/settings';
import type { PageStats, PickItem, Readable, TranslateResult } from '../shared/messages';
import { categorize } from './category';
import { harvestNames, hasTranslatableText, mask, maskAroundMarkers, unmask, MARKER_RE } from './mask';
import { injectPageStyle, TOOLTIP_CSS } from './pageStyle';
import { applyTranslation, isInlineFlow, scan, serializeGroup, TRANSLATABLE_ATTRS, UI_ATTR, type Applied, type Container, type Group, type Serialized } from './segment';
import { decide, type Decision } from './verify';

export interface EngineSettings {
  /** Langue d'arrivée quand la page est en fulfulde ; sinon on traduit vers le fulfulde. */
  ffTarget: 'fr' | 'en';
  variety: Variety | null;
  display: DisplayMode;
  prudence: boolean;
  confidenceThreshold: number;
  extraNames: string[];
}

export interface EngineDeps {
  doc: Document;
  translate: (req: TranslateRequest) => Promise<TranslateResult>;
  log: (entry: Partial<LogEntry>) => void;
  onStats: (s: PageStats) => void;
  /** Avertissement ou erreur nouvellement affiché (texte masqué) : pour la lecture automatique. */
  onWarning?: (maskedText: string) => void;
  settings: EngineSettings;
  batchSize?: number;
  debounceMs?: number;
}

type SegState = 'pending' | 'inflight' | 'translated' | 'kept' | 'error' | 'skipped';
type KeepReason = Exclude<Decision, { apply: true }>['reason'] | 'server' | 'apply';

export interface Seg {
  id: string;
  kind: 'text' | 'attr';
  group?: Group;
  ser?: Serialized;
  el?: Element;
  attr?: string;
  /** Texte d'origine (avec repères pour un segment texte). Reste en mémoire locale. */
  original: string;
  masked: string;
  values: Map<string, string>;
  placeholders: string[];
  category: CategoryHint;
  state: SegState;
  reason?: KeepReason;
  errorCode?: string;
  /** Traduction masquée telle que reçue (pour la voix et les signalements). */
  maskedTranslation?: string;
  translation?: string;
  status?: string;
  confidence?: number;
  applied: Applied | null;
  attrWritten?: string;
  marker: Element | null;
  retries: number;
}

let segCounter = 0;

/** Segment proposé au sélecteur de passages : l'élément de page est gardé en local. */
export interface PickSeg extends PickItem {
  range: () => Range | null;
}

/** Empreinte FNV-1a 32 bits : clé stable d'un segment, identique d'une visite à l'autre. */
export function segmentKey(maskedSource: string): string {
  const s = maskedSource.replace(/\{\/?[BE]\d+\}/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase();
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return 'k' + (h >>> 0).toString(16).padStart(8, '0');
}

function groupRange(group: Group): Range | null {
  const first = group.nodes[0];
  const last = group.nodes[group.nodes.length - 1];
  if (!first?.isConnected || !last?.isConnected) return null;
  const doc = first.ownerDocument;
  if (!doc) return null;
  const r = doc.createRange();
  try {
    r.setStartBefore(first);
    r.setEndAfter(last);
  } catch {
    return null;
  }
  return r;
}

export class Engine {
  readonly deps: EngineDeps;
  settings: EngineSettings;
  enabled = false;
  showingOriginal = false;
  readonly segs = new Map<string, Seg>();
  private byNode = new WeakMap<Node, Seg>();
  private byAttr = new WeakMap<Element, Map<string, Seg>>();
  private written = new WeakMap<Text, string>();
  private queue: Seg[] = [];
  private inflight = 0;
  private flushTimer: ReturnType<typeof setTimeout> | null = null;
  private dirty = new Set<Node>();
  private dirtyTimer: ReturnType<typeof setTimeout> | null = null;
  private statsTimer: ReturnType<typeof setTimeout> | null = null;
  private observer: MutationObserver | null = null;
  private observedRoots = new WeakSet<Node>();
  private markerSegs = new Map<Element, Set<Seg>>();
  /** Noms appris sur la page (mémoire locale uniquement). */
  private learnedNames = new Set<string>();
  private tooltip: { host: HTMLElement; tip: HTMLElement } | null = null;
  readonly metrics = { scanMs: 0, lastBatchMs: 0, startedAt: 0, idleAt: 0, requests: 0 };
  /** Langue de la page, détectée automatiquement à l'activation. */
  pageLang: PageLang = 'fr';

  constructor(deps: EngineDeps) {
    this.deps = deps;
    this.settings = deps.settings;
  }

  // ---------- cycle de vie ----------

  enable(): void {
    if (this.enabled) return;
    this.enabled = true;
    this.showingOriginal = false;
    this.metrics.startedAt = performance.now();
    this.pageLang = detectPageLanguage(this.deps.doc);
    injectPageStyle(this.deps.doc);
    this.observer = new MutationObserver((records) => this.onMutations(records));
    this.observe(this.deps.doc.documentElement);
    this.deps.doc.addEventListener('click', this.onClick, true);
    this.deps.doc.addEventListener('mouseover', this.onHover, true);
    this.deps.doc.addEventListener('focusin', this.onHover, true);
    this.scanAndQueue(this.deps.doc.body ?? this.deps.doc.documentElement);
    this.emitStats();
  }

  disable(): void {
    if (!this.enabled) return;
    this.enabled = false;
    this.observer?.disconnect();
    this.observer = null;
    this.observedRoots = new WeakSet();
    this.deps.doc.removeEventListener('click', this.onClick, true);
    this.deps.doc.removeEventListener('mouseover', this.onHover, true);
    this.deps.doc.removeEventListener('focusin', this.onHover, true);
    this.queue = [];
    if (this.flushTimer) clearTimeout(this.flushTimer);
    for (const seg of this.segs.values()) this.unapply(seg);
    this.markerSegs.forEach((_, el) => this.clearMarker(el));
    this.markerSegs.clear();
    this.segs.clear();
    this.byNode = new WeakMap();
    this.byAttr = new WeakMap();
    this.hideTooltip();
    this.emitStats();
  }

  /** Bascule globale vers l'original (instantanée, sans nouvel appel au serveur). */
  setShowOriginal(on: boolean): void {
    this.showingOriginal = on;
    for (const seg of this.segs.values()) {
      if (seg.state !== 'translated') continue;
      if (on) this.unapply(seg);
      else this.apply(seg);
    }
    this.markerSegs.forEach((_, el) => this.refreshMarker(el));
    this.observer?.takeRecords();
    this.emitStats();
  }

  updateSettings(next: EngineSettings): void {
    const prev = this.settings;
    this.settings = next;
    const langChanged = prev.ffTarget !== next.ffTarget || prev.variety !== next.variety;
    const ruleChanged = prev.prudence !== next.prudence || prev.confidenceThreshold !== next.confidenceThreshold || prev.extraNames.join() !== next.extraNames.join();
    if (!this.enabled) return;
    if (langChanged || ruleChanged) {
      this.disable();
      this.enable();
    } else if (prev.display !== next.display) {
      for (const seg of this.segs.values()) this.unapply(seg);
      if (!this.showingOriginal) for (const seg of this.segs.values()) if (seg.state === 'translated') this.apply(seg);
      this.observer?.takeRecords();
    }
  }

  /** Relance les segments en erreur. */
  retry(): void {
    for (const seg of this.segs.values()) {
      if (seg.state === 'error' || (seg.state === 'kept' && seg.reason === 'server')) {
        seg.state = 'pending';
        seg.retries = 0;
        this.queue.push(seg);
      }
    }
    this.scheduleFlush();
    this.emitStats();
  }

  // ---------- capture ----------

  private observe(root: Node) {
    if (!this.observer || this.observedRoots.has(root)) return;
    this.observedRoots.add(root);
    this.observer.observe(root, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ['class', 'style', 'hidden', 'open', 'aria-hidden', 'lang', ...TRANSLATABLE_ATTRS],
    });
  }

  scanAndQueue(root: Container): void {
    const t0 = performance.now();
    const res = scan(root, { owned: (n) => this.written.has(n as Text) });
    for (const sr of res.shadowRoots) {
      this.observe(sr);
      injectPageStyle(sr);
    }
    // 1er passage : apprendre les noms complets visibles, pour masquer ensuite un prénom isolé
    for (const group of res.groups) for (const n of harvestNames(serializeGroup(group).text.replace(MARKER_RE, ' '))) this.learnedNames.add(n);
    for (const a of res.attrs) for (const n of harvestNames(a.value)) this.learnedNames.add(n);
    for (const group of res.groups) this.considerGroup(group);
    for (const a of res.attrs) this.considerAttr(a.el, a.attr, a.value);
    this.metrics.scanMs += performance.now() - t0;
    this.scheduleFlush();
    this.emitStats();
  }

  private considerGroup(group: Group) {
    const ser = serializeGroup(group);
    const textNodes = ser.slots.flat();
    const ours = textNodes.filter((t) => this.written.has(t));
    if (ours.length && ours.every((t) => this.written.get(t) === t.data) && textNodes.every((t) => this.written.has(t) || !t.data.trim())) {
      return; // c'est notre propre traduction, intacte
    }
    const existing = this.byNode.get(group.nodes[0]);
    if (existing && existing.original === ser.text && !ours.length) return; // inchangé
    if (ours.length) {
      // Le site a réécrit une partie d'un texte que nous avions traduit : on remet l'original
      // là où notre traduction est encore intacte, puis on retraduit le bloc entier.
      const prev = textNodes.map((t) => this.byNode.get(t)).find(Boolean);
      if (prev) this.forget(prev, true);
      else textNodes.forEach((t) => this.written.delete(t));
      this.markDirty(group.parent);
      return;
    }
    if (existing) this.forget(existing, true);

    const m = maskAroundMarkers(ser.text, { names: this.names() });
    const seg: Seg = {
      id: `s${++segCounter}`,
      kind: 'text',
      group,
      ser,
      original: ser.text,
      masked: m.text,
      values: m.values,
      placeholders: [...m.placeholders, ...(m.text.match(/\{\/?[BE]\d+\}/g) ?? [])],
      category: categorize(group.parent, ser.text.replace(MARKER_RE, ' ')),
      state: hasTranslatableText(m.text) ? 'pending' : 'skipped',
      applied: null,
      marker: group.parent.nodeType === 1 ? (group.parent as Element) : null,
      retries: 0,
    };
    this.register(seg);
    textNodes.forEach((t) => this.byNode.set(t, seg));
    this.byNode.set(group.nodes[0], seg);
  }

  private considerAttr(el: Element, attr: string, value: string) {
    let map = this.byAttr.get(el);
    const existing = map?.get(attr);
    if (existing) {
      if (existing.applied && existing.attrWritten === value) return;
      if (!existing.applied && existing.original === value) return;
      this.forget(existing, false);
    }
    const m = mask(value, { names: this.names() });
    const seg: Seg = {
      id: `s${++segCounter}`,
      kind: 'attr',
      el,
      attr,
      original: value,
      masked: m.text,
      values: m.values,
      placeholders: m.placeholders,
      category: categorize(el, value, attr),
      state: hasTranslatableText(m.text) ? 'pending' : 'skipped',
      applied: null,
      marker: null,
      retries: 0,
    };
    if (!map) this.byAttr.set(el, (map = new Map()));
    map.set(attr, seg);
    this.register(seg);
  }

  private names(): string[] {
    return [...this.settings.extraNames, ...this.learnedNames];
  }

  private register(seg: Seg) {
    this.segs.set(seg.id, seg);
    if (seg.state === 'pending') this.queue.push(seg);
  }

  private forget(seg: Seg, restore: boolean) {
    if (restore) this.unapply(seg);
    this.segs.delete(seg.id);
    this.queue = this.queue.filter((s) => s !== seg);
    if (seg.marker) {
      this.markerSegs.get(seg.marker)?.delete(seg);
      this.refreshMarker(seg.marker);
    }
  }

  private onMutations(records: MutationRecord[]) {
    if (!this.enabled) return;
    for (const r of records) {
      const target = r.target;
      if (target.nodeType === Node.ELEMENT_NODE && (target as Element).closest(`[${UI_ATTR}],[data-amira-ignore]`)) continue;
      if (r.type === 'characterData') {
        if (this.written.get(target as Text) === (target as Text).data) continue;
        if (target.parentNode) this.dirty.add(target.parentNode);
      } else if (r.type === 'attributes') {
        const el = target as Element;
        const seg = this.byAttr.get(el)?.get(r.attributeName!);
        if (seg?.applied && seg.attrWritten === el.getAttribute(r.attributeName!)) continue;
        this.dirty.add(el);
      } else {
        let relevant = false;
        r.addedNodes.forEach((n) => {
          if (n.nodeType === Node.ELEMENT_NODE && (n as Element).hasAttribute(UI_ATTR)) return;
          if (n.nodeType === Node.TEXT_NODE && this.written.has(n as Text)) return;
          relevant = true;
        });
        if (relevant || r.removedNodes.length) this.dirty.add(target);
      }
    }
    if (!this.dirty.size) return;
    if (this.dirtyTimer) clearTimeout(this.dirtyTimer);
    this.dirtyTimer = setTimeout(() => this.processDirty(), this.deps.debounceMs ?? 150);
  }

  private markDirty(node: Node) {
    this.dirty.add(node);
    if (this.dirtyTimer) clearTimeout(this.dirtyTimer);
    this.dirtyTimer = setTimeout(() => this.processDirty(), this.deps.debounceMs ?? 150);
  }

  private processDirty() {
    this.dirtyTimer = null;
    const memo = new WeakMap<Element, boolean>();
    const roots = new Set<Container>();
    for (const node of this.dirty) {
      if (!node.isConnected) continue;
      let el: Node | null = node;
      // remonte jusqu'au bloc qui contient la phrase entière
      while (el && el.nodeType === Node.ELEMENT_NODE && isInlineFlow(el as Element, memo) && el.parentNode) el = el.parentNode;
      if (el && (el.nodeType === Node.ELEMENT_NODE || el.nodeType === Node.DOCUMENT_FRAGMENT_NODE)) {
        roots.add(el as Container);
      } else if (el && el.nodeType === Node.DOCUMENT_NODE) roots.add((el as Document).body);
    }
    this.dirty.clear();
    // ne garde que les racines les plus hautes
    const list = [...roots].filter((r) => ![...roots].some((o) => o !== r && o.contains(r)));
    for (const r of list) this.scanAndQueue(r);
    this.prune();
    this.redetect();
  }

  /**
   * Le site peut changer de langue sans recharger la page (bouton « EN »…). On re-détecte sur les
   * textes D'ORIGINE du site (jamais sur nos traductions), puis sur l'attribut lang.
   * Les segments pas encore envoyés partent avec la nouvelle langue source.
   */
  private redetect() {
    const sample = [...this.segs.values()]
      .filter((s) => s.kind === 'text' && s.state !== 'skipped')
      .map((s) => s.original.replace(MARKER_RE, ' '))
      .join(' ');
    const attr = (this.deps.doc.documentElement.getAttribute('lang') || '').toLowerCase();
    const fromAttr: PageLang | null = attr.startsWith('ff') ? 'ff' : attr.startsWith('en') ? 'en' : attr.startsWith('fr') ? 'fr' : null;
    const lang = detectLanguage(sample) ?? fromAttr ?? this.pageLang;
    if (lang === this.pageLang) return;
    this.pageLang = lang;
    this.deps.log({ niveau: 'info', source: 'client', code: 'LANG_CHANGED', message: `Langue de la page : ${lang}` });
    // ce qui reste à traduire part dans le bon sens ; ce qui était traduit depuis l'ancienne langue est refait
    for (const seg of this.segs.values()) {
      if (seg.state === 'translated' || seg.state === 'kept' || seg.state === 'error') {
        this.unapply(seg);
        seg.state = 'pending';
        seg.retries = 0;
        this.queue.push(seg);
      }
    }
    this.markerSegs.forEach((_, el) => this.refreshMarker(el));
    this.observer?.takeRecords();
    this.scheduleFlush();
    this.emitStats();
  }

  /** Oublie les segments dont le contenu a quitté la page. */
  private prune() {
    for (const seg of this.segs.values()) {
      const node = seg.kind === 'text' ? seg.group!.nodes[0] : seg.el!;
      const alive = seg.kind === 'text' ? seg.ser!.slots.flat().some((t) => t.isConnected) || node.isConnected : node.isConnected;
      if (!alive) this.forget(seg, false);
    }
  }

  // ---------- envoi ----------

  private scheduleFlush() {
    if (this.flushTimer || !this.queue.length) return;
    this.flushTimer = setTimeout(() => {
      this.flushTimer = null;
      void this.flush();
    }, 30);
  }

  private async flush() {
    while (this.queue.length && this.inflight < 2 && this.enabled) {
      const batch = this.queue.splice(0, this.deps.batchSize ?? 40).filter((s) => s.state === 'pending' && this.segs.has(s.id));
      if (!batch.length) continue;
      this.inflight++;
      batch.forEach((s) => (s.state = 'inflight'));
      this.emitStats();
      void this.send(batch).finally(() => {
        this.inflight--;
        if (this.queue.length) this.scheduleFlush();
        else if (!this.inflight) this.metrics.idleAt = performance.now();
        this.emitStats();
      });
    }
  }

  private async send(batch: Seg[]) {
    const s = this.settings;
    // sens automatique : français/anglais → fulfulde, ou fulfulde → français/anglais
    const fromFf = this.pageLang === 'ff';
    const req: TranslateRequest = {
      requestId: newRequestId(),
      source: this.pageLang,
      target: fromFf ? s.ffTarget : 'ff',
      variety: s.variety,
      segments: batch.map((seg) => ({ id: seg.id, text: seg.masked, categoryHint: seg.category, placeholders: seg.placeholders })),
    };
    const t0 = performance.now();
    let res: TranslateResult;
    try {
      res = await this.deps.translate(req);
    } catch {
      res = { ok: false, code: 'EXTENSION_UNREACHABLE', message: 'Service de l’extension indisponible' };
      this.deps.log({ niveau: 'error', source: 'extension', code: 'EXTENSION_UNREACHABLE', message: 'Message vers l’arrière-plan perdu' });
    }
    this.metrics.lastBatchMs = performance.now() - t0;
    this.metrics.requests++;
    if (!this.enabled) return;

    if (!res.ok) {
      const retryable = res.code === 'RATE_LIMITED' || res.code === 'TIMEOUT';
      for (const seg of batch) {
        if (!this.segs.has(seg.id)) continue;
        if (retryable && seg.retries < 1) {
          seg.retries++;
          seg.state = 'pending';
          this.queue.push(seg);
        } else {
          seg.state = 'error';
          seg.reason = 'server';
          seg.errorCode = res.code;
          this.setMarker(seg);
        }
      }
      if (retryable) setTimeout(() => this.scheduleFlush(), Math.min(res.retryAfterMs ?? 2000, 10_000));
      return;
    }

    const byId = new Map(res.data.segments.map((o) => [o.id, o]));
    const reasons: Record<string, number> = {};
    for (const seg of batch) {
      if (!this.segs.has(seg.id)) continue;
      const out = byId.get(seg.id);
      const d = decide({
        sentMasked: seg.masked,
        received: out,
        category: seg.category,
        prudence: s.prudence,
        threshold: s.confidenceThreshold,
      });
      seg.status = out?.status;
      seg.confidence = out?.confidence;
      if (!d.apply) {
        seg.state = 'kept';
        seg.reason = d.reason;
        reasons[d.reason] = (reasons[d.reason] ?? 0) + 1;
        this.setMarker(seg);
        continue;
      }
      seg.maskedTranslation = out!.text;
      seg.translation = unmask(out!.text, seg.values);
      seg.state = 'translated';
      if (!this.showingOriginal) {
        try {
          this.apply(seg);
        } catch {
          seg.state = 'kept';
          seg.reason = 'apply';
          reasons.apply = (reasons.apply ?? 0) + 1;
          this.unapply(seg);
          this.setMarker(seg);
          continue;
        }
      }
      if ((seg.category === 'security_warning' || seg.category === 'error') && this.deps.onWarning) {
        this.deps.onWarning(out!.text.replace(/\{\/?[BE]\d+\}/g, ''));
      }
    }
    this.observer?.takeRecords();
    if (reasons.markers) this.deps.log({ niveau: 'warn', source: 'client', code: 'MARKERS_MISMATCH', message: `${reasons.markers} segments gardés en version originale`, requestId: req.requestId });
    if (reasons.apply) this.deps.log({ niveau: 'error', source: 'client', code: 'APPLY_FAILED', message: `${reasons.apply} segments non appliqués`, requestId: req.requestId });
    const kept = Object.entries(reasons).filter(([k]) => k !== 'markers' && k !== 'apply');
    if (kept.length) {
      this.deps.log({ niveau: 'info', source: 'client', code: 'SEGMENTS_KEPT', message: kept.map(([k, v]) => `${k} ${v}`).join(', '), requestId: req.requestId });
    }
  }

  // ---------- affichage ----------

  private apply(seg: Seg) {
    if (seg.applied || !seg.translation) return;
    if (seg.kind === 'attr') {
      const el = seg.el!;
      const attr = seg.attr!;
      el.setAttribute(attr, seg.translation);
      seg.attrWritten = seg.translation;
      seg.applied = {
        written: new Map(),
        restore: () => {
          if (el.getAttribute(attr) === seg.attrWritten) el.setAttribute(attr, seg.original);
        },
      };
      return;
    }
    if (this.settings.display === 'bilingual' && seg.marker) {
      seg.applied = { written: new Map(), restore: () => undefined };
      this.setMarker(seg);
      return;
    }
    const applied = applyTranslation(seg.group!, seg.ser!, seg.translation);
    applied.written.forEach((v, t) => {
      this.written.set(t, v);
      this.byNode.set(t, seg);
    });
    seg.applied = applied;
    this.setMarker(seg);
  }

  private unapply(seg: Seg) {
    if (!seg.applied) return;
    const applied = seg.applied;
    seg.applied = null;
    applied.restore();
    applied.written.forEach((_, t) => this.written.delete(t));
    if (seg.marker) this.refreshMarker(seg.marker);
  }

  private setMarker(seg: Seg) {
    if (!seg.marker) return;
    let set = this.markerSegs.get(seg.marker);
    if (!set) this.markerSegs.set(seg.marker, (set = new Set()));
    set.add(seg);
    this.refreshMarker(seg.marker);
  }

  private clearMarker(el: Element) {
    el.removeAttribute('data-amira-state');
    el.removeAttribute('data-amira-bi');
    el.removeAttribute('data-amira-hover');
  }

  private refreshMarker(el: Element) {
    const segs = [...(this.markerSegs.get(el) ?? [])].filter((s) => this.segs.has(s.id));
    this.clearMarker(el);
    // « Voir l'original » : la page redevient strictement identique, sans aucune marque d'Amira
    if (!segs.length || this.showingOriginal) return;
    if (segs.some((s) => s.state === 'kept' || s.state === 'error')) el.setAttribute('data-amira-state', 'kept');
    else if (segs.some((s) => s.applied)) el.setAttribute('data-amira-state', 'tr');
    if (this.settings.display === 'bilingual') {
      const bi = segs.filter((s) => s.applied && s.kind === 'text').map((s) => s.translation!.replace(/\{\/?[BE]\d+\}/g, '')).join(' / ');
      if (bi) el.setAttribute('data-amira-bi', bi);
    }
    if (this.settings.display === 'hover' && segs.some((s) => s.applied)) el.setAttribute('data-amira-hover', '');
  }

  // ---------- interactions dans la page ----------

  /** Alt+clic sur un passage traduit : bascule ce passage seul entre original et traduction. */
  private onClick = (ev: MouseEvent) => {
    if (!ev.altKey) return;
    const el = (ev.target as Element | null)?.closest?.('[data-amira-state]');
    const segs = el ? [...(this.markerSegs.get(el) ?? [])].filter((s) => s.state === 'translated') : [];
    if (!segs.length) return;
    ev.preventDefault();
    ev.stopPropagation();
    const anyApplied = segs.some((s) => s.applied);
    segs.forEach((s) => (anyApplied ? this.unapply(s) : this.apply(s)));
    this.observer?.takeRecords();
  };

  private onHover = (ev: Event) => {
    const target = ev.target as Element | null;
    const el = target?.closest?.('[data-amira-hover], [data-amira-state="kept"]');
    if (!el) return this.hideTooltip();
    const segs = [...(this.markerSegs.get(el) ?? [])];
    const kept = segs.some((s) => s.state === 'kept' || s.state === 'error');
    const text = kept
      ? this.deps.doc.documentElement.lang?.startsWith('en')
        ? 'Kept in the original language: the translation was not reliable enough.'
        : 'Gardé dans la langue d’origine : la traduction n’était pas assez sûre.'
      : segs.filter((s) => s.applied).map((s) => s.original.replace(MARKER_RE, '')).join(' / ');
    if (!text) return this.hideTooltip();
    this.showTooltip(el, kept ? 'Amira' : 'Original', text);
  };

  private showTooltip(anchor: Element, title: string, text: string) {
    const doc = this.deps.doc;
    if (!this.tooltip) {
      const host = doc.createElement('div');
      host.setAttribute(UI_ATTR, '');
      host.setAttribute('data-amira-ignore', '');
      const root = host.attachShadow({ mode: 'closed' });
      const style = doc.createElement('style');
      style.textContent = TOOLTIP_CSS;
      const tip = doc.createElement('div');
      tip.className = 'tip';
      tip.setAttribute('role', 'tooltip');
      root.append(style, tip);
      doc.documentElement.appendChild(host);
      this.tooltip = { host, tip };
      this.observer?.takeRecords();
    }
    const { tip } = this.tooltip;
    tip.replaceChildren();
    const b = doc.createElement('b');
    b.textContent = title;
    tip.append(b, doc.createTextNode(text));
    tip.hidden = false;
    const r = anchor.getBoundingClientRect();
    const view = doc.defaultView!;
    tip.style.left = `${Math.max(8, Math.min(r.left, view.innerWidth - 370))}px`;
    tip.style.top = `${r.bottom + 6 + 60 > view.innerHeight ? Math.max(8, r.top - 66) : r.bottom + 6}px`;
  }

  private hideTooltip() {
    if (this.tooltip) this.tooltip.tip.hidden = true;
  }

  // ---------- état ----------

  stats(): PageStats {
    let translated = 0, kept = 0, errors = 0, pending = 0, total = 0;
    for (const seg of this.segs.values()) {
      if (seg.state === 'skipped') continue;
      total++;
      if (seg.state === 'translated') translated++;
      else if (seg.state === 'kept') kept++;
      else if (seg.state === 'error') errors++;
      else pending++;
    }
    let hote: string | undefined;
    try {
      hote = this.deps.doc.location?.hostname || undefined;
    } catch {
      /* about:blank */
    }
    return { enabled: this.enabled, showingOriginal: this.showingOriginal, translated, kept, errors, pending, total, hote, lang: this.enabled ? this.pageLang : detectPageLanguage(this.deps.doc) };
  }

  private emitStats() {
    if (this.statsTimer) return;
    this.statsTimer = setTimeout(() => {
      this.statsTimer = null;
      this.deps.onStats(this.stats());
    }, 100);
  }

  /** Identifiants stables des segments repérés quand la traduction est éteinte. */
  private dryIds = new WeakMap<Node, string>();

  /**
   * Segments que l'on peut choisir pour la lecture, dans l'ordre de la page.
   * Traduction active : les segments du moteur. Sinon : la même segmentation, calculée à la demande,
   * sans rien envoyer au serveur.
   */
  pickables(): PickSeg[] {
    const strip = (t: string) => t.replace(/\{\/?[BE]\d+\}/g, '').replace(/\s+/g, ' ').trim();
    const preview = (g: Group, fallback: string) => {
      const r = groupRange(g);
      const txt = (r?.toString() ?? '').replace(/\s+/g, ' ').trim();
      return txt || fallback.replace(MARKER_RE, ' ').replace(/\s+/g, ' ').trim();
    };
    if (this.enabled) {
      return [...this.segs.values()]
        .filter((s) => s.kind === 'text' && s.state !== 'skipped' && s.group)
        .map((s) => ({
          id: s.id,
          key: segmentKey(s.masked),
          text: strip(s.state === 'translated' && s.maskedTranslation && !this.showingOriginal ? s.maskedTranslation : s.masked),
          preview: preview(s.group!, s.original),
          category: s.category,
          range: () => groupRange(s.group!),
        }));
    }
    const doc = this.deps.doc;
    const res = scan(doc.body ?? doc.documentElement);
    const names = [...this.names()];
    for (const g of res.groups) for (const n of harvestNames(serializeGroup(g).text.replace(MARKER_RE, ' '))) names.push(n);
    const out: PickSeg[] = [];
    for (const g of res.groups) {
      const ser = serializeGroup(g);
      const m = maskAroundMarkers(ser.text, { names });
      if (!hasTranslatableText(m.text)) continue;
      let id = this.dryIds.get(g.nodes[0]);
      if (!id) this.dryIds.set(g.nodes[0], (id = `p${++segCounter}`));
      out.push({
        id,
        key: segmentKey(m.text),
        text: strip(m.text),
        preview: preview(g, ser.text),
        category: categorize(g.parent, ser.text.replace(MARKER_RE, ' ')),
        range: () => groupRange(g),
      });
    }
    return out;
  }

  /** Textes MASQUÉS à lire à voix haute. */
  readable(what: 'page' | 'selection' | 'messages' | 'report'): Readable {
    if (what === 'report') {
      // signalement : texte d'origine MASQUÉ et traduction affichée MASQUÉE
      return {
        segments: [...this.segs.values()]
          .filter((s) => s.state === 'translated' && s.maskedTranslation)
          .map((s) => ({ id: s.id, text: s.masked.replace(/\{\/?[BE]\d+\}/g, ''), shown: s.maskedTranslation!.replace(/\{\/?[BE]\d+\}/g, ''), category: s.category })),
      };
    }
    if (what === 'selection') {
      const sel = this.deps.doc.getSelection?.()?.toString() ?? '';
      return sel.trim() ? { segments: [{ id: 'sel', text: mask(sel, { names: this.settings.extraNames }).text }] } : { segments: [] };
    }
    const list = [...this.segs.values()].filter((s) => s.kind === 'text' && s.state !== 'skipped');
    const chosen = what === 'messages' ? list.filter((s) => s.category === 'error' || s.category === 'security_warning') : list;
    return {
      segments: chosen.map((s) => ({
        id: s.id,
        text: (s.state === 'translated' && s.maskedTranslation ? s.maskedTranslation : s.masked).replace(/\{\/?[BE]\d+\}/g, ''),
        category: s.category,
        key: segmentKey(s.masked),
      })),
    };
  }
}
