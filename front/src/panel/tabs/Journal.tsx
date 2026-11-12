import { useEffect, useId, useMemo, useState } from 'react';
import { clearLog, exportLog, LOG_KEY, readLog, type LogEntry } from '../../services/log';
import type { BgResult, Readable } from '../../shared/messages';
import { errorText } from '../App';
import { bg, readable } from '../bridge';
import { useT } from '../i18n';
import { mask } from '../../content/mask';
import { IconCopy, IconDownload, IconFlag, IconTrash } from '../ui/icons';
import { ScribbleUnderline } from '../ui/Scribbles';
import type { TabProps } from './Translate';

type Filter = 'all' | 'client' | 'serveur' | 'extension' | 'error';

export function JournalTab({ showToast }: TabProps) {
  const { t, lang } = useT();
  const [entries, setEntries] = useState<LogEntry[] | null>(null);
  const [filter, setFilter] = useState<Filter>('all');
  const [open, setOpen] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<'log' | 'cache' | null>(null);

  useEffect(() => {
    void readLog().then(setEntries);
    const onChange = (changes: Record<string, chrome.storage.StorageChange>, area: string) => {
      if (area === 'local' && changes[LOG_KEY]) void readLog().then(setEntries);
    };
    chrome.storage.onChanged.addListener(onChange);
    return () => chrome.storage.onChanged.removeListener(onChange);
  }, []);

  const shown = useMemo(() => {
    const all = [...(entries ?? [])].reverse();
    if (filter === 'all') return all;
    if (filter === 'error') return all.filter((e) => e.niveau === 'error');
    return all.filter((e) => e.source === filter);
  }, [entries, filter]);

  const fmt = new Intl.DateTimeFormat(lang === 'en' ? 'en-GB' : 'fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  // 'log' : le journal ; 'cache' : les traductions gardées par l'arrière-plan (chrome.storage.local)
  const confirmClear = async () => {
    if (confirming === 'log') await clearLog();
    else {
      await bg<BgResult<null>>({ type: 'amira:clearCache' });
      showToast(t('journal.cacheCleared'));
    }
    setConfirming(null);
  };

  const download = () => {
    const blob = new Blob([exportLog(shown)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `amira-journal-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };

  return (
    <>
      <section className="bloc">
        <h1 className="grand-titre" style={{ fontSize: '2.3rem' }}>{t('journal.title')}</h1>
        <p className="aide">{t('journal.intro')}</p>
      </section>

      <div className="segments" role="group" aria-label={t('journal.title')}>
        {(['all', 'client', 'serveur', 'extension', 'error'] as Filter[]).map((f) => (
          <label className="segment" key={f}>
            <input type="radio" name="jf" checked={filter === f} onChange={() => setFilter(f)} />
            <span>{t(`journal.filters.${f}`)}</span>
          </label>
        ))}
      </div>

      <div className="ligne">
        <button className="pastille" aria-label={t('journal.copy')} title={t('journal.copy')} disabled={!shown.length}
          onClick={() => void navigator.clipboard.writeText(exportLog(shown)).then(() => showToast(t('translate.copied')))}>
          <IconCopy />
        </button>
        <button className="pastille" aria-label={t('journal.export')} title={t('journal.export')} disabled={!shown.length} onClick={download}>
          <IconDownload />
        </button>
        {confirming ? (
          <>
            <span style={{ fontWeight: 600 }}>{t(confirming === 'log' ? 'journal.confirmClear' : 'journal.confirmClearCache')}</span>
            <button className="btn rose" onClick={() => void confirmClear()}>
              {t(confirming === 'log' ? 'journal.clear' : 'journal.clearCache')}
            </button>
            <button className="lien" onClick={() => setConfirming(null)}>{t('onboarding.skip')}</button>
          </>
        ) : (
          <>
            <button className="pastille" aria-label={t('journal.clear')} title={t('journal.clear')} disabled={!entries?.length} onClick={() => setConfirming('log')}>
              <IconTrash />
            </button>
            <button className="lien" onClick={() => setConfirming('cache')}>{t('journal.clearCache')}</button>
          </>
        )}
      </div>

      {entries === null ? (
        <p role="status">{t('states.loading')}</p>
      ) : shown.length === 0 ? (
        <div className="vide-etat">
          <h2>{t('journal.empty').split('.')[0]}.</h2>
          <ScribbleUnderline style={{ position: 'static' }} />
          <p className="aide">{t('journal.empty').split('.').slice(1).join('.').trim()}</p>
        </div>
      ) : (
        <ul className="evenements">
          {shown.slice(0, 200).map((e) => (
            <li className="evenement" key={e.id}>
              <button aria-expanded={open === e.id} onClick={() => setOpen(open === e.id ? null : e.id)}>
                <i className={`niveau ${e.niveau}`} aria-label={t(`journal.levels.${e.niveau}`)} />
                <span>
                  <code>{e.code}</code>
                  <span className="meta"> · {t(`journal.filters.${e.source}`)}{e.httpStatus ? ` · HTTP ${e.httpStatus}` : ''}{e.durationMs != null ? ` · ${e.durationMs} ms` : ''}</span>
                  <br />
                  <span className="meta">{e.message}{e.hote ? ` — ${e.hote}` : ''}</span>
                </span>
                <span className="heure">{fmt.format(e.ts)}</span>
              </button>
              {open === e.id && <pre aria-label={t('journal.detail')}>{JSON.stringify(e, null, 2)}</pre>}
            </li>
          ))}
        </ul>
      )}

      <ReportForm showToast={showToast} />
    </>
  );
}

function ReportForm({ showToast }: { showToast: (m: string) => void }) {
  const { t } = useT();
  const [items, setItems] = useState<Readable['segments'] | null>(null);
  const [pick, setPick] = useState('');
  const [suggestion, setSuggestion] = useState('');
  const [sending, setSending] = useState(false);
  const id = useId();
  const current = items?.find((i) => i.id === pick);

  const load = async () => {
    try {
      const r = await readable('report');
      setItems(r.segments);
      setPick(r.segments[0]?.id ?? '');
    } catch (e) {
      showToast(errorText(t, e));
    }
  };

  const send = async () => {
    if (!current) return;
    setSending(true);
    const res = await bg<BgResult<null>>({
      type: 'amira:feedback',
      req: { segmentId: current.id, originalMasked: current.text, shown: current.shown ?? '', suggestion: mask(suggestion.trim()).text },
    }).catch(() => ({ ok: false, code: 'generic', message: '' }) as BgResult<null>);
    setSending(false);
    if (res.ok) {
      setSuggestion('');
      showToast(t('journal.reportSent'));
    } else showToast(errorText(t, new Error(res.code)));
  };

  return (
    <section className="section" style={{ borderTop: '2px solid var(--trait)', paddingTop: 20 }} aria-labelledby={id}>
      <h2 id={id}>{t('journal.report')}</h2>
      <p className="aide">{t('journal.reportIntro')}</p>
      {items === null ? (
        <button className="btn secondaire" style={{ alignSelf: 'flex-start' }} onClick={() => void load()}>
          <IconFlag /> {t('journal.reportPick')}
        </button>
      ) : !items.length ? (
        <p className="note">{t('journal.reportNone')}</p>
      ) : (
        <>
          <label className="champ">
            <span>{t('journal.reportOriginal')}</span>
            <select value={pick} onChange={(e) => setPick(e.target.value)}>
              {items.map((i) => (
                <option key={i.id} value={i.id}>{i.text.slice(0, 80)}</option>
              ))}
            </select>
          </label>
          <div className="champ">
            <span>{t('journal.reportShown')}</span>
            <div className="resultat">{current?.shown}</div>
          </div>
          <label className="champ">
            <span>{t('journal.reportSuggestion')}</span>
            <textarea value={suggestion} onChange={(e) => setSuggestion(e.target.value)} />
          </label>
          <button className="btn" style={{ alignSelf: 'flex-start' }} disabled={!suggestion.trim() || sending} onClick={() => void send()}>
            {t('journal.reportSend')}
          </button>
        </>
      )}
    </section>
  );
}
