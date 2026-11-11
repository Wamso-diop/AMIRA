import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import logo from '../assets/amira-logo.png';
import logoClair from '../assets/amira-logo-clair.png';
import type { Settings } from '../services/settings';
import type { ServerState } from '../shared/messages';
import { toTab, NoContentError } from './bridge';
import { ensureContent } from './access';
import { usePageStats, useSettings, useStatus } from './hooks';
import { I18n, makeT, type T } from './i18n';
import { Onboarding } from './Onboarding';
import { JournalTab } from './tabs/Journal';
import { SettingsTab } from './tabs/Settings';
import { TranslateTab } from './tabs/Translate';
import { VoiceTab } from './tabs/Voice';
import { StatusPill, Switch, Toast, useToast } from './ui/controls';

type TabKey = 'translate' | 'voice' | 'settings' | 'journal';
const TABS: TabKey[] = ['translate', 'voice', 'settings', 'journal'];

function applyAppearance(s: Settings) {
  const root = document.documentElement;
  if (s.theme === 'system') delete root.dataset.theme;
  else root.dataset.theme = s.theme;
  if (s.highContrast) root.dataset.contrast = 'high';
  else delete root.dataset.contrast;
  if (s.reduceMotion) root.dataset.motion = 'reduce';
  else delete root.dataset.motion;
  root.style.setProperty('--zoom', String(s.textScale));
  root.lang = s.uiLanguage;
}

export function errorText(t: T, e: unknown): string {
  const code = e instanceof NoContentError ? 'NO_CONTENT' : (e as Error)?.message;
  const txt = t(`errors.${code}`);
  return txt.startsWith('errors.') ? t('errors.generic') : txt;
}

export function App() {
  const [settings, update] = useSettings();
  const lang = settings?.uiLanguage ?? 'fr';
  const t = useMemo(() => makeT(lang), [lang]);
  const { status, checking, refresh } = useStatus([settings?.mockScenario]);
  const page = usePageStats();
  const [tab, setTab] = useState<TabKey>('translate');
  const [toast, showToast] = useToast();
  const [online, setOnline] = useState(navigator.onLine);
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  useEffect(() => {
    if (settings) applyAppearance(settings);
  }, [settings]);

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, []);

  if (!settings) {
    return <div className="chargement" role="status">{t('states.loading')}</div>;
  }

  const ctx = { t, lang };

  if (!settings.onboarded) {
    return (
      <I18n.Provider value={ctx}>
        <Onboarding onDone={() => void update({ onboarded: true })} />
      </I18n.Provider>
    );
  }

  let state: ServerState | 'loading' = status ? status.state : 'loading';
  if (!online && !status?.demo) state = 'offline';
  else if (state === 'ready' && (page.stats.pending > 0 || checking)) state = 'busy';

  const toggle = async (on: boolean): Promise<boolean> => {
    try {
      if (on) await ensureContent(update);
      page.setStats(await toTab({ type: 'amira:setEnabled', enabled: on }));
      return true;
    } catch (e) {
      showToast(errorText(t, e));
      return false;
    }
  };

  const onTabKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = TABS.indexOf(tab);
    let next = i;
    if (e.key === 'ArrowRight') next = (i + 1) % TABS.length;
    else if (e.key === 'ArrowLeft') next = (i - 1 + TABS.length) % TABS.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = TABS.length - 1;
    else return;
    e.preventDefault();
    setTab(TABS[next]);
    tabRefs.current[TABS[next]]?.focus();
  };

  const common = { settings, update, status, refresh, page, showToast };

  return (
    <I18n.Provider value={ctx}>
      <div className="app">
        <header className="entete">
          <div className="entete-l1">
            <picture>
              <source srcSet={logoClair} media={settings.theme === 'system' ? '(prefers-color-scheme: dark)' : settings.theme === 'dark' ? 'all' : 'not all'} />
              <img className="logo" src={logo} alt="Amira" />
            </picture>
            <StatusPill state={state} demo={status?.demo} />
          </div>
          <div className="entete-l2">
            <p className="accroche">{t('app.tagline')}</p>
            <Switch className="entete-switch" label={t('app.toggle')} checked={page.stats.enabled} onChange={(v) => void toggle(v)} />
          </div>
          <div className="onglets" role="tablist" aria-label="Amira" onKeyDown={onTabKey}>
            {TABS.map((k) => (
              <button
                key={k}
                ref={(el) => (tabRefs.current[k] = el)}
                role="tab"
                id={`tab-${k}`}
                aria-controls={`panel-${k}`}
                aria-selected={tab === k}
                tabIndex={tab === k ? 0 : -1}
                className="onglet"
                onClick={() => setTab(k)}
              >
                {t(`app.tabs.${k}`)}
              </button>
            ))}
          </div>
        </header>
        <main className="contenu" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
          {tab === 'translate' && <TranslateTab {...common} toggle={toggle} />}
          {tab === 'voice' && <VoiceTab {...common} />}
          {tab === 'settings' && <SettingsTab {...common} />}
          {tab === 'journal' && <JournalTab {...common} />}
        </main>
        <Toast msg={toast} />
      </div>
    </I18n.Provider>
  );
}
