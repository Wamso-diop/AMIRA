import { useEffect, useId, useRef, useState } from 'react';
import { newRequestId, type SegmentStatus } from '../../services/api';
import { isTarget, TARGET } from '../../languages';
import type { DisplayMode, Settings } from '../../services/settings';
import type { PageStats, StatusResult, TranslateResult } from '../../shared/messages';
import { mask, unmask } from '../../content/mask';
import { detectLanguage } from '../../content/lang';
import { decide } from '../../content/verify';
import { errorText } from '../App';
import { bg, toTab } from '../bridge';
import { useT } from '../i18n';
import { langLabel } from '../langLabel';
import { play } from '../player';
import { Badge, Segmented } from '../ui/controls';
import { IconCopy, IconListen, IconRetry } from '../ui/icons';
import { Petals } from '../ui/Petals';
import { HandArrow } from '../ui/Scribbles';

export interface TabProps {
  settings: Settings;
  update: (p: Partial<Settings>) => Promise<void>;
  status: StatusResult | null;
  refresh: () => Promise<void>;
  page: { stats: PageStats; setStats: (s: PageStats) => void; reachable: boolean | null; refresh: () => Promise<void> };
  showToast: (m: string) => void;
}

type Lang = string;

/** Sens de traduction : français/anglais → langue cible ; langue cible → français ou anglais. Jamais français ↔ anglais. */
export function direction(from: Lang, settings: Settings): { source: Lang; target: Lang } {
  return isTarget(from) ? { source: from, target: settings.returnLang } : { source: from, target: TARGET.code };
}

export function ServerBanner({ status, refresh }: TabProps) {
  const { t } = useT();
  if (!status || (status.state !== 'offline' && status.state !== 'error')) return null;
  const offline = status.state === 'offline';
  return (
    <section className="annonce alerte" role="alert">
      <h2>{offline ? t('states.offlineTitle') : t('states.errorTitle')}</h2>
      <p>{offline ? t('states.offlineBody') : t('states.errorBody', { code: status.errorCode ?? '—' })}</p>
      <div className="ligne">
        <button className="btn" onClick={() => void refresh()}>
          <IconRetry /> {t('states.retry')}
        </button>
      </div>
    </section>
  );
}

const Arrow = () => (
  <svg viewBox="0 0 24 24" aria-hidden>
    <path d="M4 12h15M13 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export function TranslateTab(props: TabProps & { toggle: (on: boolean) => Promise<boolean> }) {
  const { settings, update, page, showToast, status } = props;
  const { t, lang: uiLang } = useT();
  const s = page.stats;
  const pageLang: Lang = s.lang ?? 'fr';
  const dir = direction(pageLang, settings);

  const retry = async () => {
    await props.refresh();
    try {
      page.setStats(await toTab({ type: 'amira:retry' }));
    } catch (e) {
      showToast(errorText(t, e));
    }
  };

  const targetWord = isTarget(dir.target) ? TARGET.name[uiLang] : dir.target === 'en' ? 'English' : t('translate.frWord');

  return (
    <>
      <ServerBanner {...props} />

      <section className="accueil-zone" aria-labelledby="hero">
        <HandArrow />
        <h1 id="hero" className="grand-titre" style={{ paddingRight: 70 }}>
          {t('hero.line1')}
          <span className="ligne2">
            {t('hero.line2pre')}
            <span className="surligne">{targetWord}</span>
          </span>
        </h1>
        <div className="petales-ligne">
          <Petals active={0} label={t('translate.target')} />
          <p>{t('translate.soonList')}</p>
        </div>
      </section>

      <p className="sens" aria-live="polite">
        <span>{t('translate.detected')}</span>
        <b>{langLabel(t, dir.source)}</b>
        <Arrow />
        <b>{langLabel(t, dir.target)}</b>
      </p>

      <BigButton {...props} />

      <ul className="chiffres" aria-live="polite">
        <li className="ok"><i aria-hidden /><b>{s.translated}</b><span>{t('translate.counters.translated')}</span></li>
        <li className="garde"><i aria-hidden /><b>{s.kept}</b><span>{t('translate.counters.kept')}</span></li>
        <li className={`err ${s.errors ? 'actif' : ''}`}><i aria-hidden /><b>{s.errors}</b><span>{t('translate.counters.errors')}</span></li>
      </ul>
      {s.errors > 0 && status?.state !== 'offline' && (
        <button className="btn secondaire" style={{ alignSelf: 'center' }} onClick={() => void retry()}>
          <IconRetry /> {t('states.retry')}
        </button>
      )}
      <section className="section options" aria-labelledby="opt">
        <h2 id="opt">{t('translate.options')}</h2>
        {isTarget(pageLang) && (
          <Segmented<'fr' | 'en'>
            legend={t('translate.returnLang')}
            value={settings.returnLang}
            onChange={(v) => void update({ returnLang: v })}
            options={[{ value: 'fr', label: t('translate.fr') }, { value: 'en', label: t('translate.en') }]}
          />
        )}
        <div className="bloc">
          <Segmented<DisplayMode>
            legend={t('translate.display')}
            value={settings.display}
            onChange={(v) => void update({ display: v })}
            options={(['replace', 'bilingual', 'hover'] as DisplayMode[]).map((v) => ({ value: v, label: t(`translate.displays.${v}`) }))}
          />
          <p className="aide">{t(`translate.displayHelp.${settings.display}`)}</p>
        </div>
        <p className="aide">{t('translate.altClickHint')}</p>
      </section>

      <QuickTranslator {...props} />

      <section className="fiabilite" aria-labelledby="legende">
        <h3 id="legende">{t('translate.legend')}</h3>
        <ul>
          {(['validated', 'machine', 'uncertain'] as SegmentStatus[]).map((st) => (
            <li key={st} className={st}>
              <Badge status={st} />
              <span>{t(`translate.badgeHelp.${st}`)}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

/** Traducteur rapide : la langue du texte saisi est détectée, le sens suit la même règle que la page. */
function QuickTranslator({ settings, showToast }: TabProps) {
  const { t } = useT();
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<{ text: string; status: SegmentStatus; kept: boolean; target: Lang } | null>(null);
  const id = useId();
  const typed: Lang = (input.trim() && detectLanguage(input)) || 'fr';
  const dir = direction(typed, settings);

  const run = async () => {
    if (!input.trim()) return;
    setBusy(true);
    const m = mask(input);
    const res = await bg<TranslateResult>({
      type: 'amira:translate',
      req: {
        requestId: newRequestId(),
        source: dir.source,
        target: dir.target,
        variety: settings.variety,
        segments: [{ id: 'q1', text: m.text, placeholders: m.placeholders }],
      },
    }).catch(() => ({ ok: false, code: 'generic', message: '' }) as TranslateResult);
    setBusy(false);
    if (!res.ok) {
      setOut(null);
      showToast(errorText(t, new Error(res.code)));
      return;
    }
    const seg = res.data.segments[0];
    const d = decide({ sentMasked: m.text, received: seg, prudence: settings.prudence, threshold: settings.confidenceThreshold });
    if (!d.apply) setOut({ text: input, status: 'uncertain', kept: true, target: dir.target });
    else setOut({ text: unmask(seg.text, m.values), status: seg.status, kept: false, target: dir.target });
  };

  return (
    <section className="bloc" aria-labelledby={id}>
      <h2 id={id}>{t('translate.quick')}</h2>
      <label className="sr-only" htmlFor={id + 'in'}>{t('translate.quickPlaceholder')}</label>
      <textarea
        id={id + 'in'}
        value={input}
        placeholder={t('translate.quickPlaceholder')}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) void run();
        }}
      />
      {input.trim() && (
        <p className="sens petit">
          <b>{langLabel(t, dir.source)}</b>
          <Arrow />
          <b>{langLabel(t, dir.target)}</b>
        </p>
      )}
      <p className="aide">{t('translate.quickMasked')}</p>
      <div className="ligne">
        <button className="btn" onClick={() => void run()} disabled={busy || !input.trim()}>
          {busy ? t('states.loading') : t('translate.quickGo')}
        </button>
        <span style={{ flex: 1 }} />
        <button
          className="pastille"
          aria-label={t('translate.copy')}
          title={t('translate.copy')}
          disabled={!out}
          onClick={() => out && void navigator.clipboard.writeText(out.text).then(() => showToast(t('translate.copied')))}
        >
          <IconCopy />
        </button>
        <button
          className="pastille"
          aria-label={t('translate.listen')}
          title={t('translate.listen')}
          disabled={!out || out.kept}
          onClick={() => out && void play([mask(out.text).text], out.target, settings.ttsSpeed)}
        >
          <IconListen />
        </button>
      </div>
      <div className={`resultat ${out ? '' : 'vide'}`} aria-live="polite">
        {out ? (
          <>
            <Badge status={out.status} />
            <span>{out.text}</span>
            {out.kept && <span className="aide">{t('translate.quickKept')}</span>}
          </>
        ) : (
          t('translate.result')
        )}
      </div>
    </section>
  );
}

type Phase = 'off' | 'waiting' | 'translated' | 'original';

/**
 * Gros bouton circulaire : « Traduire » ↔ « Voir l'original ».
 * Pendant l'attente de la réponse du back-end, les pétales tournent autour et l'anneau se remplit.
 */
function BigButton({ page, showToast, toggle }: TabProps & { toggle: (on: boolean) => Promise<boolean> }) {
  const { t } = useT();
  const s = page.stats;
  const [waiting, setWaiting] = useState(false);
  const [clics, setClics] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // fin d'attente : la page a répondu et plus rien n'est en cours
  useEffect(() => {
    if (waiting && s.enabled && s.pending === 0 && (s.total === 0 || s.translated + s.kept + s.errors > 0)) setWaiting(false);
  }, [waiting, s.enabled, s.pending, s.total, s.translated, s.kept, s.errors]);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const phase: Phase = waiting || (s.enabled && s.pending > 0) ? 'waiting' : !s.enabled ? 'off' : s.showingOriginal ? 'original' : 'translated';
  const done = s.translated + s.kept + s.errors;
  const progress = s.total ? Math.min(1, done / s.total) : 0;

  const onClick = async () => {
    setClics((n) => n + 1);
    if (phase === 'off') {
      setWaiting(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setWaiting(false), 20000);
      const ok = await toggle(true);
      if (!ok) setWaiting(false);
      return;
    }
    try {
      page.setStats(await toTab({ type: 'amira:showOriginal', on: phase === 'translated' }));
    } catch (e) {
      showToast(errorText(t, e));
    }
  };

  const label = phase === 'waiting' ? t('translate.translating') : phase === 'translated' ? t('translate.seeOriginal') : t('translate.translate');
  const hint =
    phase === 'waiting' ? t('translate.waiting') : phase === 'translated' ? t('translate.seeingTranslation') : phase === 'original' ? t('hero.showingOriginal') : t('hero.off');
  const R = 90;
  const C = 2 * Math.PI * R;

  return (
    <div className="rond-zone">
      <div className={`rond-cadre ${phase}`}>
        <svg className="rond-deco" viewBox="-110 -110 220 220" aria-hidden>
          <circle className="rond-halo" r={104} />
          {phase === 'waiting' && (
            <>
              <circle className="rond-arc" r={R} strokeDasharray={`${C * Math.max(0.12, progress)} ${C}`} />
              <g className="rond-orbite">
                {['var(--rose)', 'var(--vert)', 'var(--jaune)', 'var(--bleu)'].map((c, i) => (
                  <circle key={c} cx={0} cy={-R} r={5.5} fill={c} transform={`rotate(${i * 22})`} />
                ))}
              </g>
            </>
          )}
        </svg>
        <button
          className={`rond ${phase}`}
          onClick={() => void onClick()}
          disabled={phase === 'waiting'}
          aria-pressed={phase === 'translated'}
          aria-busy={phase === 'waiting'}
        >
          <span key={clics} className="rond-onde" aria-hidden />
          <span key={phase} className="rond-libelle">
            {phase === 'waiting' ? (
              <span className="rond-points" aria-hidden><i /><i /><i /></span>
            ) : phase === 'translated' ? (
              <svg viewBox="0 0 24 24" aria-hidden><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" fill="none" stroke="currentColor" strokeWidth="2.2" /><circle cx="12" cy="12" r="3" fill="currentColor" /></svg>
            ) : (
              <svg viewBox="0 0 24 24" aria-hidden><path d="M4 5h9M8.5 3v2M6 5c0 4 3 7 6 8M11 5c0 3-3 7-7 9M13 21l4-9 4 9M14.5 18h5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>
            )}
            <span>{label}</span>
          </span>
        </button>
      </div>
      <p className="rond-aide" aria-live="polite">{hint}</p>
    </div>
  );
}
