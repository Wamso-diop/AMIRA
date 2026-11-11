/**
 * Sélecteur de passages (onglet Voix → « La sélection »).
 * La page est déjà découpée en segments (même découpage que la traduction et que les
 * enregistrements des locuteurs natifs) : on ne sélectionne pas du texte au curseur, on choisit
 * des segments entiers. Chaque segment est entouré sur la page ; un clic le prend ou le retire.
 * L'interface vit dans un shadow DOM fermé : elle ne touche ni au style ni au texte du site.
 */
import type { PickSeg } from './engine';
import type { PickCommand, PickState } from '../shared/messages';
import { UI_ATTR } from './segment';

const MAX_ZONES = 400;

const WORDS = {
  fr: {
    hint: 'Touchez les passages à faire lire',
    shift: 'Maj + clic : choisir une suite',
    clear: 'Effacer',
    done: 'Terminé',
    add: 'Ajouter à la lecture',
    remove: 'Retirer de la lecture',
    reading: 'En lecture',
  },
  en: {
    hint: 'Tap the passages to read aloud',
    shift: 'Shift + click: pick a run',
    clear: 'Clear',
    done: 'Done',
    add: 'Add to reading',
    remove: 'Remove from reading',
    reading: 'Reading',
  },
};

export const PICKER_CSS = `
:host{all:initial}
.couche{position:fixed;inset:0;pointer-events:none;z-index:2147483646}
.zone{position:fixed;pointer-events:auto;box-sizing:border-box;margin:0;padding:0;
  border:2px dashed rgba(72,28,75,.5);border-radius:7px;background:rgba(43,177,235,.07);cursor:pointer;
  transition:background-color .15s ease,border-color .15s ease,box-shadow .2s ease}
.zone:hover,.zone:focus-visible,.zone.survol{border:2px solid #E01D5B;background:rgba(224,29,91,.11);outline:none}
.zone.choisi{border:3px solid #E01D5B;background:rgba(239,209,9,.30)}
.zone.lecture{border:3px solid #481C4B;background:rgba(239,209,9,.42);box-shadow:0 0 0 5px rgba(239,209,9,.55)}
.couche.passive .zone{pointer-events:none}
.num,.plus{position:absolute;top:-13px;left:-15px;min-width:24px;height:24px;padding:0 6px;box-sizing:border-box;
  border-radius:999px;font:800 12px/24px system-ui,sans-serif;text-align:center;box-shadow:0 0 0 2px #fff;pointer-events:none}
.num{display:none;background:#E01D5B;color:#fff}
.zone.choisi .num{display:block}
.plus{display:none;background:#481C4B;color:#fff;font-size:16px;line-height:22px}
.zone:hover:not(.choisi) .plus,.zone:focus-visible:not(.choisi) .plus{display:block}
.onde{display:none;position:absolute;right:-12px;top:-12px;height:24px;padding:0 8px;border-radius:999px;align-items:center;gap:2px;
  background:#481C4B;box-shadow:0 0 0 2px #EFD109;pointer-events:none}
.onde i{display:block;width:3px;height:10px;border-radius:2px;background:#EFD109;animation:onde .9s ease-in-out infinite}
.onde i:nth-child(2){animation-delay:.15s}.onde i:nth-child(3){animation-delay:.3s}
.zone.lecture .onde{display:flex}
.barre{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:2147483647;box-sizing:border-box;
  display:flex;align-items:center;gap:10px;flex-wrap:nowrap;white-space:nowrap;
  max-width:calc(100vw - 24px);padding:8px 8px 8px 14px;border-radius:28px;
  background:#481C4B;color:#fff;font:600 14px/1.25 system-ui,sans-serif;
  box-shadow:0 10px 32px rgba(72,28,75,.38),0 0 0 2px #EFD109;animation:entre .35s cubic-bezier(.2,.9,.3,1.2)}
.barre[hidden]{display:none}
.marque{display:flex;align-items:center;gap:7px;font-weight:800}
.marque svg{width:18px;height:18px}
.msg{min-width:0;overflow:hidden;text-overflow:ellipsis}
.msg small{display:block;font-weight:500;opacity:.75;font-size:12px;overflow:hidden;text-overflow:ellipsis}
@media (max-width:560px){.msg small,.marque span{display:none}.barre{gap:8px;padding-left:10px}}
.compte{min-width:26px;height:26px;padding:0 8px;box-sizing:border-box;border-radius:999px;background:#EFD109;color:#481C4B;
  font:800 13px/26px system-ui,sans-serif;text-align:center}
.barre button{min-height:36px;padding:0 14px;border-radius:999px;border:2px solid rgba(255,255,255,.85);background:transparent;color:#fff;
  font:700 13px/1 system-ui,sans-serif;cursor:pointer}
.barre button:hover{background:rgba(255,255,255,.14)}
.barre button:focus-visible{outline:3px solid #EFD109;outline-offset:2px}
.barre .fini{background:#E01D5B;border-color:#E01D5B}
.barre .fini:hover{background:#c2134c}
@keyframes onde{0%,100%{transform:scaleY(.4)}50%{transform:scaleY(1.2)}}
@keyframes entre{from{opacity:0;transform:translate(-50%,16px)}}
@media (prefers-reduced-motion:reduce){.zone,.barre,.onde i{transition:none;animation:none}}
`;

const LOGO =
  '<svg viewBox="-30 -30 60 60" aria-hidden="true">' +
  ['#E01D5B', '#2DCF42', '#EFD109', '#2BB1EB']
    .map((c, i) => `<path d="M0 -8 C 6 -13 7.5 -17 7.5 -21 A 7.5 7.5 0 0 0 -7.5 -21 C -7.5 -17 -6 -13 0 -8 Z" transform="rotate(${[15, -60, -125, 165][i]})" fill="${c}"/>`)
    .join('') +
  '</svg>';

export class Picker {
  private items: PickSeg[] = [];
  private selected = new Set<string>();
  private active = false;
  private reading: string | null = null;
  private hover: string | null = null;
  private hoverTimer: ReturnType<typeof setTimeout> | null = null;
  private lastClicked: string | null = null;
  private ui: { host: HTMLElement; layer: HTMLElement; bar: HTMLElement; count: HTMLElement; msg: HTMLElement } | null = null;
  private zones = new Map<string, HTMLButtonElement>();
  private raf = 0;
  private observer: MutationObserver | null = null;
  private refreshTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly doc: Document,
    private readonly source: () => PickSeg[],
    private readonly emit: (s: PickState) => void,
    private readonly lang: () => 'fr' | 'en' = () => 'fr',
  ) {}

  handle(cmd: PickCommand): PickState {
    switch (cmd.action) {
      case 'list':
        this.items = this.source();
        break;
      case 'start':
        this.selected = new Set(cmd.selected);
        this.start();
        break;
      case 'stop':
        this.stop();
        break;
      case 'set':
        this.selected = new Set(cmd.selected);
        this.schedule();
        break;
      case 'focus':
        this.focus(cmd.id, !!cmd.flash);
        break;
    }
    return this.state();
  }

  state(): PickState {
    const ids = new Set(this.items.map((i) => i.id));
    return {
      // les fonctions (range) ne passent pas par la messagerie
      items: this.items.map(({ id, key, text, preview, category }) => ({ id, key, text, preview, category })),
      selected: [...this.selected].filter((id) => ids.has(id)).sort((a, b) => this.index(a) - this.index(b)),
      active: this.active,
    };
  }

  private index(id: string) {
    return this.items.findIndex((i) => i.id === id);
  }

  // ---------- cycle de vie ----------

  private start() {
    this.items = this.source();
    this.active = true;
    this.mount();
    this.schedule();
    const view = this.doc.defaultView!;
    this.doc.addEventListener('keydown', this.onKey, true);
    if (!this.observer && this.doc.body) {
      this.observer = new MutationObserver(() => {
        if (this.refreshTimer) clearTimeout(this.refreshTimer);
        this.refreshTimer = setTimeout(() => {
          this.items = this.source();
          this.schedule();
          this.emit(this.state());
        }, 400);
      });
      this.observer.observe(this.doc.body, { childList: true, subtree: true, characterData: true });
    }
    view.requestAnimationFrame(() => this.ui?.bar.querySelector<HTMLButtonElement>('.fini')?.focus({ preventScroll: true }));
  }

  private stop() {
    if (!this.active) return;
    this.active = false;
    this.doc.removeEventListener('keydown', this.onKey, true);
    this.observer?.disconnect();
    this.observer = null;
    if (this.refreshTimer) clearTimeout(this.refreshTimer);
    this.lastClicked = null;
    this.unmountIfIdle();
    this.schedule();
  }

  private focus(id: string | null, flash: boolean) {
    if (flash) {
      this.hover = id;
      if (this.hoverTimer) clearTimeout(this.hoverTimer);
      if (id) this.hoverTimer = setTimeout(() => ((this.hover = null), this.schedule(), this.unmountIfIdle()), 1600);
    } else {
      this.reading = id;
    }
    if (id) {
      if (!this.items.some((i) => i.id === id)) this.items = this.source();
      this.mount();
      this.scrollTo(id);
    }
    this.schedule();
    this.unmountIfIdle();
  }

  private scrollTo(id: string) {
    const r = this.items.find((i) => i.id === id)?.range();
    if (!r) return;
    const rect = r.getBoundingClientRect();
    const view = this.doc.defaultView!;
    if (rect.top >= 60 && rect.bottom <= view.innerHeight - 90) return;
    let el: Node | null = r.startContainer;
    if (el && el.nodeType !== 1) el = el.parentNode;
    const target = (r.commonAncestorContainer.nodeType === 1 ? r.commonAncestorContainer : r.commonAncestorContainer.parentNode) as Element | null;
    const reduce = view.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    (target ?? (el as Element | null))?.scrollIntoView?.({ block: 'center', behavior: reduce ? 'auto' : 'smooth' });
  }

  // ---------- interface dans la page ----------

  private mount() {
    if (this.ui) {
      this.ui.bar.hidden = !this.active;
      return;
    }
    const doc = this.doc;
    const w = WORDS[this.lang()];
    const host = doc.createElement('div');
    host.setAttribute(UI_ATTR, '');
    host.setAttribute('data-amira-ignore', '');
    const root = host.attachShadow({ mode: 'closed' });
    const style = doc.createElement('style');
    style.textContent = PICKER_CSS;
    const layer = doc.createElement('div');
    layer.className = 'couche';
    const bar = doc.createElement('div');
    bar.className = 'barre';
    bar.setAttribute('role', 'toolbar');
    bar.setAttribute('aria-label', 'Amira');
    const brand = doc.createElement('span');
    brand.className = 'marque';
    brand.innerHTML = LOGO; // contenu fixe, défini ci-dessus
    brand.append('Amira');
    const msg = doc.createElement('span');
    msg.className = 'msg';
    msg.textContent = w.hint;
    const small = doc.createElement('small');
    small.textContent = w.shift;
    msg.append(small);
    const count = doc.createElement('span');
    count.className = 'compte';
    count.setAttribute('aria-live', 'polite');
    const clear = doc.createElement('button');
    clear.type = 'button';
    clear.textContent = w.clear;
    clear.addEventListener('click', () => {
      this.selected.clear();
      this.changed();
    });
    const done = doc.createElement('button');
    done.type = 'button';
    done.className = 'fini';
    done.textContent = w.done;
    done.addEventListener('click', () => {
      this.stop();
      this.emit(this.state());
    });
    bar.append(brand, msg, count, clear, done);
    bar.hidden = !this.active;
    root.append(style, layer, bar);
    doc.documentElement.appendChild(host);
    this.ui = { host, layer, bar, count, msg };
    const view = doc.defaultView!;
    view.addEventListener('scroll', this.schedule, true);
    view.addEventListener('resize', this.schedule);
  }

  private unmountIfIdle() {
    if (this.active || this.reading || this.hover || !this.ui) return;
    const view = this.doc.defaultView!;
    view.removeEventListener('scroll', this.schedule, true);
    view.removeEventListener('resize', this.schedule);
    this.ui.host.remove();
    this.ui = null;
    this.zones.clear();
  }

  private schedule = () => {
    if (!this.ui || this.raf) return;
    const view = this.doc.defaultView!;
    this.raf = view.requestAnimationFrame(() => {
      this.raf = 0;
      this.render();
    });
  };

  private render() {
    const ui = this.ui;
    if (!ui) return;
    const view = this.doc.defaultView!;
    const w = WORDS[this.lang()];
    const vh = view.innerHeight;
    const vw = view.innerWidth;
    const order = this.state().selected;
    ui.count.textContent = String(order.length);
    ui.bar.hidden = !this.active;
    ui.layer.classList.toggle('passive', !this.active);

    // en lecture seule (sélecteur fermé) : seuls les passages lus ou survolés depuis le panneau sont entourés
    const shown = this.active ? this.items : this.items.filter((i) => i.id === this.reading || i.id === this.hover);
    const seen = new Set<string>();
    for (const item of shown) {
      if (seen.size >= MAX_ZONES) break;
      const range = item.range();
      if (!range) continue;
      const r = range.getBoundingClientRect();
      if (r.width < 2 || r.height < 2 || r.bottom < -40 || r.top > vh + 40 || r.right < 0 || r.left > vw) continue;
      seen.add(item.id);
      let z = this.zones.get(item.id);
      if (!z) {
        z = this.makeZone(item.id);
        this.zones.set(item.id, z);
        ui.layer.append(z);
      }
      const pad = 5;
      z.style.left = `${r.left - pad}px`;
      z.style.top = `${r.top - pad}px`;
      z.style.width = `${r.width + pad * 2}px`;
      z.style.height = `${r.height + pad * 2}px`;
      const n = order.indexOf(item.id);
      z.classList.toggle('choisi', n >= 0);
      z.classList.toggle('lecture', item.id === this.reading);
      z.classList.toggle('survol', item.id === this.hover);
      z.querySelector('.num')!.textContent = n >= 0 ? String(n + 1) : '';
      z.setAttribute('aria-pressed', String(n >= 0));
      z.tabIndex = this.active ? 0 : -1;
      const excerpt = item.preview.length > 80 ? item.preview.slice(0, 79) + '…' : item.preview;
      z.setAttribute('aria-label', `${item.id === this.reading ? w.reading : n >= 0 ? w.remove : w.add} : ${excerpt}`);
    }
    for (const [id, z] of this.zones) {
      if (!seen.has(id)) {
        z.remove();
        this.zones.delete(id);
      }
    }
  }

  private makeZone(id: string): HTMLButtonElement {
    const doc = this.doc;
    const z = doc.createElement('button');
    z.type = 'button';
    z.className = 'zone';
    const num = doc.createElement('span');
    num.className = 'num';
    const plus = doc.createElement('span');
    plus.className = 'plus';
    plus.textContent = '+';
    const onde = doc.createElement('span');
    onde.className = 'onde';
    onde.append(doc.createElement('i'), doc.createElement('i'), doc.createElement('i'));
    z.append(num, plus, onde);
    z.addEventListener('click', (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      if (!this.active) return;
      this.toggle(id, ev.shiftKey);
    });
    return z;
  }

  private toggle(id: string, run: boolean) {
    if (run && this.lastClicked && this.lastClicked !== id) {
      const a = this.index(this.lastClicked);
      const b = this.index(id);
      if (a >= 0 && b >= 0) {
        for (let i = Math.min(a, b); i <= Math.max(a, b); i++) this.selected.add(this.items[i].id);
        this.lastClicked = id;
        return this.changed();
      }
    }
    if (this.selected.has(id)) this.selected.delete(id);
    else this.selected.add(id);
    this.lastClicked = id;
    this.changed();
  }

  private changed() {
    this.schedule();
    this.emit(this.state());
  }

  private onKey = (ev: KeyboardEvent) => {
    if (ev.key !== 'Escape' || !this.active) return;
    ev.stopPropagation();
    this.stop();
    this.emit(this.state());
  };
}
