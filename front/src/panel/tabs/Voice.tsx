import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { useT } from '../i18n';
import { errorText } from '../App';
import { readLangFor } from '../autoRead';
import { IDLE, pause, play, resume, setRate, skip, stop, subscribe, type PlayerState } from '../player';
import { Switch } from '../ui/controls';
import { IconAlert, IconMic, IconNext, IconPage, IconPlay, IconPrev, IconStop, IconTarget } from '../ui/icons';
import { Petals } from '../ui/Petals';
import { HandArrow } from '../ui/Scribbles';
import { ServerBanner, type TabProps } from './Translate';
import type { BgResult, ContentEvent, PickItem, PickState } from '../../shared/messages';
import { isTarget, TARGET } from '../../languages';
import { bg, toTab } from '../bridge';

type What = 'page' | 'selection' | 'messages';

const isMessage = (i: PickItem) => i.category === 'error' || i.category === 'security_warning';

/** Commande au sélecteur de passages de la page ; silencieuse si la page n'est pas joignable. */
async function pick(cmd: Parameters<typeof toTab>[0]): Promise<PickState | null> {
  try {
    return await toTab<PickState>(cmd);
  } catch {
    return null;
  }
}

export function VoiceTab(props: TabProps) {
  const { settings, update, status, showToast, page } = props;
  const { t, lang: uiLang } = useT();
  // langue lue : celle de la traduction affichée (langue cible, ou français/anglais si la page est dans la langue cible)
  const readLang = readLangFor(page.stats.lang, settings);
  const langWord = isTarget(readLang) ? TARGET.name[uiLang] : readLang === 'en' ? 'English' : t('translate.frWord');
  const [what, setWhat] = useState<What>('page');
  const [player, setPlayer] = useState<PlayerState>(IDLE);
  const [items, setItems] = useState<PickItem[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [picking, setPicking] = useState(false);
  const tts = !!status?.capabilities?.tts;
  const stt = !!status?.capabilities?.stt;

  useEffect(() => subscribe(setPlayer), []);
  useEffect(() => {
    if (player.error) showToast(errorText(t, new Error(player.error)));
  }, [player.error, showToast, t]);

  const applyState = useCallback((s: PickState | null) => {
    if (!s) return;
    setItems(s.items);
    setSelected(s.selected);
    setPicking(s.active);
  }, []);

  // passages de la page : rechargés quand la page change (traduction, original, navigation)
  const s = page.stats;
  useEffect(() => {
    void pick({ type: 'amira:pick', action: 'list' }).then(applyState);
  }, [applyState, s.hote, s.enabled, s.showingOriginal, s.translated, s.total]);

  // le sélecteur de la page informe le panneau de chaque choix
  useEffect(() => {
    const onMsg = (msg: ContentEvent) => {
      if (msg?.type === 'amira:picked') applyState(msg.state);
    };
    chrome.runtime.onMessage.addListener(onMsg);
    return () => chrome.runtime.onMessage.removeListener(onMsg);
  }, [applyState]);

  // en quittant l'onglet : on range l'outil de la page
  useEffect(
    () => () => {
      void pick({ type: 'amira:pick', action: 'stop' });
      void pick({ type: 'amira:pick', action: 'focus', id: null });
    },
    [],
  );

  // le passage lu est entouré sur la page
  useEffect(() => {
    void pick({ type: 'amira:pick', action: 'focus', id: player.currentId });
  }, [player.currentId]);

  const startPicking = async () => applyState(await pick({ type: 'amira:pick', action: 'start', selected }));
  const stopPicking = async () => applyState(await pick({ type: 'amira:pick', action: 'stop' }));

  const chooseMode = (v: What) => {
    setWhat(v);
    // « La sélection » : l'outil de sélection apparaît aussitôt sur la page
    if (v === 'selection') void startPicking();
    else if (picking) void stopPicking();
  };

  const setSel = (ids: string[]) => {
    const order = new Map(items.map((i, n) => [i.id, n]));
    const next = [...new Set(ids)].sort((a, b) => (order.get(a) ?? 0) - (order.get(b) ?? 0));
    setSelected(next);
    void pick({ type: 'amira:pick', action: 'set', selected: next });
  };

  const messages = useMemo(() => items.filter(isMessage), [items]);
  const chosen = useMemo(() => items.filter((i) => selected.includes(i.id)), [items, selected]);
  const queue = what === 'page' ? items : what === 'messages' ? messages : chosen;

  const start = async () => {
    if (what === 'selection' && !chosen.length) {
      showToast(t('voice.picker.chooseFirst'));
      return void startPicking();
    }
    if (!queue.length) return showToast(what === 'messages' ? t('voice.noMessages') : t('voice.nothing'));
    if (picking) void stopPicking();
    try {
      await play(queue.map((i) => ({ text: i.text, id: i.id, key: i.key })), readLang, settings.ttsSpeed);
    } catch (e) {
      showToast(errorText(t, e));
    }
  };

  const current = player.currentId ? items.find((i) => i.id === player.currentId) : undefined;

  return (
    <>
      <ServerBanner {...props} />

      <section className="accueil-zone" aria-labelledby="voix-titre">
        <HandArrow />
        <h1 id="voix-titre" className="grand-titre" style={{ paddingRight: 70 }}>
          {t('voice.title')}
          <span className="ligne2">
            {t('voice.heroPre')}
            <span className="surligne">{langWord}</span>
          </span>
        </h1>
        <div className="petales-ligne">
          <Petals active={0} label={t('translate.target')} />
          <p>{t('voice.intro')}</p>
        </div>
      </section>

      {!tts ? (
        <p className="note rose" role="status">{t('voice.noTts')}</p>
      ) : (
        <>
          <Modes
            value={what}
            onChange={chooseMode}
            counts={{ page: items.length, selection: chosen.length, messages: messages.length }}
          />

          {what === 'selection' && (
            <PassagePicker
              items={items}
              selected={selected}
              picking={picking}
              onToggle={(id) => setSel(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])}
              onSet={setSel}
              onStart={() => void startPicking()}
              onStop={() => void stopPicking()}
            />
          )}

          <ListenButton
            player={player}
            count={queue.length}
            empty={what === 'selection' && !chosen.length}
            onStart={() => void start()}
          />

          <div className="lecture-barre">
            <button className="pastille" onClick={() => void skip(-1)} disabled={player.status === 'idle' || player.index === 0} aria-label={t('voice.prev')} title={t('voice.prev')}>
              <IconPrev />
            </button>
            <button className="pastille" onClick={stop} disabled={player.status === 'idle'} aria-label={t('voice.stop')} title={t('voice.stop')}>
              <IconStop />
            </button>
            <button className="pastille" onClick={() => void skip(1)} disabled={player.status === 'idle' || player.index >= player.total - 1} aria-label={t('voice.next')} title={t('voice.next')}>
              <IconNext />
            </button>
            {player.voice ? (
              <span className={`badge ${player.voice === 'recorded' ? 'validated' : 'machine'}`}>
                {player.voice === 'recorded' ? t('voice.recorded') : t('voice.synthetic')}
              </span>
            ) : (
              <span className="aide">{t('voice.voiceHint')}</span>
            )}
          </div>
          {player.missing && (
            <p className="note rose" role="status">
              {t('voice.noRecording')}
            </p>
          )}

          {current && player.status !== 'idle' && (
            <figure className="en-lecture" aria-live="polite">
              <figcaption>
                <span className="mini-onde" aria-hidden><i /><i /><i /><i /></span>
                {t('voice.nowReading')} · {player.index + 1}/{player.total}
              </figcaption>
              <blockquote>{current.preview}</blockquote>
            </figure>
          )}

          <Speed
            value={settings.ttsSpeed}
            onChange={(v) => {
              setRate(v);
              void update({ ttsSpeed: v });
            }}
          />

          <section className="section options">
            <Switch label={t('voice.autoWarnings')} checked={settings.autoReadWarnings} onChange={(v) => void update({ autoReadWarnings: v })} />
            <p className="aide">{t('voice.placeholdersNote')}</p>
          </section>
        </>
      )}

      <section className="section" style={{ borderTop: '2px solid var(--trait-doux)', paddingTop: 20 }}>
        <h2>{t('voice.dictation')}</h2>
        {stt ? <Dictation language={TARGET.code} /> : <p className="aide">{t('voice.dictationOff')}</p>}
        {!stt && (
          <button className="btn secondaire" disabled>
            <IconMic /> {t('voice.dictationStart')}
          </button>
        )}
      </section>
    </>
  );
}

/** « Que lire ? » : trois tuiles avec icône et nombre de passages. */
function Modes({ value, onChange, counts }: { value: What; onChange: (v: What) => void; counts: Record<What, number> }) {
  const { t } = useT();
  const name = useId();
  const icons: Record<What, JSX.Element> = { page: <IconPage />, selection: <IconTarget />, messages: <IconAlert /> };
  const sub = (v: What) =>
    v === 'page' ? t('voice.counts.page', { n: counts.page }) : v === 'selection' ? t('voice.counts.selection', { n: counts.selection }) : t('voice.counts.messages', { n: counts.messages });
  return (
    <fieldset className="modes">
      <legend>{t('voice.what')}</legend>
      {(['page', 'selection', 'messages'] as What[]).map((v) => (
        <label key={v} className={`mode ${v}`}>
          <input type="radio" name={name} value={v} checked={value === v} onChange={() => onChange(v)} />
          <span className="mode-carte">
            <span className="mode-icone">{icons[v]}</span>
            <b>{t(`voice.whats.${v}`)}</b>
            <small>{sub(v)}</small>
          </span>
        </label>
      ))}
    </fieldset>
  );
}

/**
 * Outil de sélection : les passages sont déjà découpés (même découpage que les enregistrements des
 * locuteurs natifs). On les choisit sur la page (zones entourées) ou dans la liste ci-dessous.
 */
function PassagePicker(props: {
  items: PickItem[];
  selected: string[];
  picking: boolean;
  onToggle: (id: string) => void;
  onSet: (ids: string[]) => void;
  onStart: () => void;
  onStop: () => void;
}) {
  const { items, selected, picking } = props;
  const { t } = useT();
  const [q, setQ] = useState('');
  const id = useId();
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const norm = (x: string) => x.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const shown = q.trim() ? items.filter((i) => norm(i.preview).includes(norm(q.trim()))) : items;

  // survoler une ligne entoure brièvement le passage sur la page
  const flash = (pid: string) => {
    if (flashTimer.current) clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => void pick({ type: 'amira:pick', action: 'focus', id: pid, flash: true }), 120);
  };
  useEffect(() => () => { if (flashTimer.current) clearTimeout(flashTimer.current); }, []);

  return (
    <section className={`selecteur ${picking ? 'actif' : ''}`} aria-labelledby={id}>
      <div className="selecteur-tete">
        <span className="selecteur-icone" aria-hidden><IconTarget /></span>
        <div>
          <h2 id={id}>{t('voice.picker.title')}</h2>
          <p className="aide">{t('voice.picker.intro')}</p>
        </div>
      </div>

      <div className="selecteur-actions">
        {picking ? (
          <button className="btn rose" onClick={props.onStop}>{t('voice.picker.finish')}</button>
        ) : (
          <button className="btn" onClick={props.onStart}><IconTarget /> {t('voice.picker.onPage')}</button>
        )}
        <span className="compte-choisis" aria-live="polite">
          <b>{selected.length}</b> {t('voice.picker.chosen', { n: selected.length })}
        </span>
      </div>
      {picking && (
        <p className="selecteur-direct" role="status">
          <span className="point-direct" aria-hidden />
          {t('voice.picker.live')}
        </p>
      )}

      {items.length > 6 && (
        <>
          <label className="sr-only" htmlFor={id + 'q'}>{t('voice.picker.search')}</label>
          <input id={id + 'q'} type="text" className="selecteur-recherche" value={q} placeholder={t('voice.picker.search')} onChange={(e) => setQ(e.target.value)} />
        </>
      )}

      {items.length === 0 ? (
        <p className="aide">{t('voice.picker.empty')}</p>
      ) : shown.length === 0 ? (
        <p className="aide">{t('voice.picker.noMatch')}</p>
      ) : (
        <ol className="passages" aria-label={t('voice.picker.title')}>
          {shown.map((i) => {
            const n = selected.indexOf(i.id);
            return (
              <li key={i.id}>
                <button
                  className={`passage ${n >= 0 ? 'choisi' : ''}`}
                  aria-pressed={n >= 0}
                  onClick={() => props.onToggle(i.id)}
                  onMouseEnter={() => flash(i.id)}
                  onFocus={() => flash(i.id)}
                >
                  <span className="passage-num" aria-hidden>{n >= 0 ? n + 1 : '+'}</span>
                  <span className="passage-texte">{i.preview}</span>
                  {isMessage(i) && <span className="passage-tag">{t('voice.picker.message')}</span>}
                </button>
              </li>
            );
          })}
        </ol>
      )}

      {items.length > 0 && (
        <div className="selecteur-pied">
          <span className="aide">{t('voice.picker.order')}</span>
          <button className="lien" onClick={() => props.onSet([...selected, ...shown.map((i) => i.id)])}>{t('voice.picker.all')}</button>
          <button className="lien" onClick={() => props.onSet([])} disabled={!selected.length}>{t('voice.picker.clear')}</button>
        </div>
      )}
    </section>
  );
}

/** Gros bouton circulaire, jumeau de celui de « Traduire » : Écouter ↔ Pause ↔ Reprendre. */
function ListenButton({ player, count, empty, onStart }: { player: PlayerState; count: number; empty: boolean; onStart: () => void }) {
  const { t } = useT();
  const [clics, setClics] = useState(0);
  const phase = empty && player.status === 'idle' ? 'empty' : player.status;
  const R = 90;
  const C = 2 * Math.PI * R;
  const progress = player.total ? (player.index + (player.status === 'loading' ? 0.15 : 0.5)) / player.total : 0;

  const onClick = () => {
    setClics((n) => n + 1);
    if (phase === 'playing' || phase === 'loading') pause();
    else if (phase === 'paused') resume();
    else onStart();
  };

  const label = phase === 'playing' || phase === 'loading' ? t('voice.pause') : phase === 'paused' ? t('voice.resume') : phase === 'empty' ? t('voice.choose') : t('voice.play');
  const hint =
    phase === 'loading' ? t('voice.hints.loading')
    : phase === 'playing' ? t('voice.hints.playing', { i: player.index + 1, n: player.total })
    : phase === 'paused' ? t('voice.hints.paused', { i: player.index + 1, n: player.total })
    : phase === 'empty' ? t('voice.hints.empty')
    : count ? t('voice.hints.idle', { n: count })
    : t('voice.nothing');

  return (
    <div className="rond-zone">
      <div className={`rond-cadre voix ${phase}`}>
        <svg className="rond-deco" viewBox="-110 -110 220 220" aria-hidden>
          <circle className="rond-halo" r={104} />
          {(phase === 'playing' || phase === 'loading' || phase === 'paused') && (
            <>
              <circle className="rond-piste" r={R} />
              <circle className="rond-arc" r={R} strokeDasharray={`${C * Math.max(0.04, Math.min(1, progress))} ${C}`} />
            </>
          )}
          {phase === 'playing' && (
            <g className="rond-vagues">
              <circle r={78} />
              <circle r={78} />
              <circle r={78} />
            </g>
          )}
          {phase === 'loading' && (
            <g className="rond-orbite">
              {['var(--rose)', 'var(--vert)', 'var(--jaune)', 'var(--bleu)'].map((c, i) => (
                <circle key={c} cx={0} cy={-R} r={5.5} fill={c} transform={`rotate(${i * 22})`} />
              ))}
            </g>
          )}
        </svg>
        <button className={`rond voix ${phase}`} onClick={onClick} aria-pressed={phase === 'playing'} aria-busy={phase === 'loading'}>
          <span key={clics} className="rond-onde" aria-hidden />
          <span key={phase} className="rond-libelle">
            {phase === 'playing' ? (
              <span className="egaliseur" aria-hidden><i /><i /><i /><i /><i /></span>
            ) : phase === 'loading' ? (
              <span className="rond-points" aria-hidden><i /><i /><i /></span>
            ) : phase === 'empty' ? (
              <IconTarget />
            ) : phase === 'paused' ? (
              <IconPlay />
            ) : (
              <svg viewBox="0 0 24 24" aria-hidden><path d="M4 9v6h4l5 4V5L8 9H4z" fill="currentColor" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" /><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" /></svg>
            )}
            <span>{label}</span>
          </span>
        </button>
      </div>
      <p className="rond-aide" aria-live="polite">{hint}</p>
    </div>
  );
}

/** Vitesse : réglette avec repères Lent / Normal / Rapide. */
function Speed({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const { t } = useT();
  const id = useId();
  const presets = [0.75, 1, 1.25];
  return (
    <div className="vitesse">
      <div className="entre">
        <label htmlFor={id}><b>{t('voice.speed')}</b></label>
        <span className="vitesse-valeur">{value.toFixed(2).replace(/0$/, '')}×</span>
      </div>
      <input id={id} type="range" min={0.5} max={1.5} step={0.05} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <div className="vitesse-reperes">
        {presets.map((p, n) => (
          <button key={p} className={`repere ${Math.abs(value - p) < 0.01 ? 'actif' : ''}`} onClick={() => onChange(p)}>
            {t(`voice.speeds.${['slow', 'normal', 'fast'][n]}`)}
          </button>
        ))}
      </div>
    </div>
  );
}

function Dictation({ language }: { language: string }) {
  const { t } = useT();
  const [rec, setRec] = useState<MediaRecorder | null>(null);
  const [text, setText] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const chunks = useRef<Blob[]>([]);

  const startRec = async () => {
    setErr(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const r = new MediaRecorder(stream);
      chunks.current = [];
      r.ondataavailable = (e) => chunks.current.push(e.data);
      r.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop());
        const blob = new Blob(chunks.current, { type: r.mimeType });
        const b64 = await new Promise<string>((res) => {
          const fr = new FileReader();
          fr.onload = () => res(String(fr.result).split(',')[1] ?? '');
          fr.readAsDataURL(blob);
        });
        const out = await bg<BgResult<{ text: string }>>({ type: 'amira:stt', audioBase64: b64, mimeType: r.mimeType, language });
        if (out.ok) setText(out.data.text);
        else setErr(errorText(t, new Error(out.code)));
      };
      r.start();
      setRec(r);
    } catch {
      setErr(t('voice.micDenied'));
    }
  };

  return (
    <div className="bloc">
      {rec ? (
        <button className="btn rose" onClick={() => { rec.stop(); setRec(null); }}><IconStop /> {t('voice.dictationStop')}</button>
      ) : (
        <button className="btn" onClick={() => void startRec()}><IconMic /> {t('voice.dictationStart')}</button>
      )}
      {err && <p className="note rose" role="alert">{err}</p>}
      {text && (
        <label className="champ">
          <span>{t('voice.dictationResult')}</span>
          <textarea value={text} onChange={(e) => setText(e.target.value)} />
        </label>
      )}
    </div>
  );
}
