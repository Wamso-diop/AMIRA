import type { Theme } from '../../services/settings';
import { setAllSites } from '../access';
import { list, useT } from '../i18n';
import { Segmented, Switch } from '../ui/controls';
import { IconCheck, IconCross, IconLock } from '../ui/icons';
import type { TabProps } from './Translate';

const BUILTIN = 'https://safinum.cm/*';

export function SettingsTab({ settings, update, showToast }: TabProps) {
  const { t, lang } = useT();

  const removeSite = async (pattern: string) => {
    await chrome.permissions.remove?.({ origins: [pattern] }).catch(() => false);
    await update({ enabledSites: settings.enabledSites.filter((p) => p !== pattern) });
  };

  return (
    <>
      <section className="section" aria-labelledby="s-sec">
        <h2 id="s-sec">{t('settings.security')}</h2>
        <Switch label={t('settings.prudence')} help={t('settings.prudenceHelp')} checked={settings.prudence} onChange={(v) => void update({ prudence: v })} />
        <label className="champ">
          <span>{t('settings.threshold')} : {Math.round(settings.confidenceThreshold * 100)} %</span>
          <input
            type="range"
            min={0.3}
            max={0.95}
            step={0.05}
            value={settings.confidenceThreshold}
            disabled={!settings.prudence}
            onChange={(e) => void update({ confidenceThreshold: Number(e.target.value) })}
          />
        </label>
        <div className="ligne" style={{ alignItems: 'flex-start', flexWrap: 'nowrap' }}>
          <Switch label={t('settings.mask')} help={t('settings.maskHelp')} checked disabled />
          <span style={{ width: 20, flex: 'none', marginTop: 12 }}><IconLock title={t('settings.maskHelp')} /></span>
        </div>
        <p className="note">{t('settings.warningRule')}</p>
      </section>

      <section className="section" aria-labelledby="s-a11y">
        <h2 id="s-a11y">{t('settings.a11y')}</h2>
        <label className="champ">
          <span>{t('settings.textSize')} : {Math.round(settings.textScale * 100)} %</span>
          <input type="range" min={0.9} max={1.3} step={0.05} value={settings.textScale} onChange={(e) => void update({ textScale: Number(e.target.value) })} />
        </label>
        <Switch label={t('settings.contrast')} checked={settings.highContrast} onChange={(v) => void update({ highContrast: v })} />
        <Segmented<Theme>
          legend={t('settings.theme')}
          value={settings.theme}
          onChange={(v) => void update({ theme: v })}
          options={(['system', 'light', 'dark'] as Theme[]).map((v) => ({ value: v, label: t(`settings.themes.${v}`) }))}
        />
        <Switch label={t('settings.motion')} checked={settings.reduceMotion} onChange={(v) => void update({ reduceMotion: v })} />
        <Segmented<'fr' | 'en'>
          legend={t('settings.uiLang')}
          value={settings.uiLanguage}
          onChange={(v) => void update({ uiLanguage: v })}
          options={[{ value: 'fr', label: 'Français' }, { value: 'en', label: 'English' }]}
        />
      </section>

      <section className="section" aria-labelledby="s-sites">
        <h2 id="s-sites">{t('settings.sites')}</h2>
        <p className="aide">{t('settings.sitesHelp')}</p>
        <Switch
          label={t('settings.allSites')}
          help={t('settings.allSitesHelp')}
          checked={settings.allSites}
          onChange={async (v) => {
            const ok = await setAllSites(v, update);
            if (!ok) showToast(t('settings.permissionDenied'));
          }}
        />
        <ul className="sites">
          {settings.enabledSites.map((p) => (
            <li key={p}>
              <span>{p.replace(/^https?:\/\//, '').replace(/\/\*$/, '')}</span>
              {p === BUILTIN ? (
                <span className="aide">{t('settings.builtin')}</span>
              ) : (
                <button className="lien" onClick={() => void removeSite(p)}>{t('settings.removeSite')}</button>
              )}
            </li>
          ))}
        </ul>
        <h3>{t('settings.shortcut')}</h3>
        <p>{t('settings.shortcutBody')}</p>
        <button className="lien" style={{ alignSelf: 'flex-start' }} onClick={() => void chrome.tabs.create({ url: 'chrome://extensions/shortcuts' })}>
          {t('settings.shortcutChange')}
        </button>
      </section>


      <section className="section" aria-labelledby="s-priv">
        <h2 id="s-priv">{t('settings.privacy')}</h2>
        <div className="confid">
          <div>
            <h3>{t('settings.sentTitle')}</h3>
            <ul>
              {list(lang, 'settings.sent').map((x) => (
                <li key={x}><IconCheck />{x}</li>
              ))}
            </ul>
          </div>
          <div>
            <h3>{t('settings.neverTitle')}</h3>
            <ul>
              {list(lang, 'settings.never').map((x) => (
                <li key={x} style={{ color: 'var(--rose-texte)' }}><IconCross /><span style={{ color: 'var(--texte)' }}>{x}</span></li>
              ))}
            </ul>
          </div>
        </div>
        <button className="lien" style={{ alignSelf: 'flex-start' }} onClick={() => void update({ onboarded: false })}>
          {t('settings.replayOnboarding')}
        </button>
      </section>
    </>
  );
}
