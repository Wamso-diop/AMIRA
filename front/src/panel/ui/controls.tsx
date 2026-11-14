import { useEffect, useId, useState } from 'react';
import type { SegmentStatus } from '../../services/api';
import type { ServerState } from '../../shared/messages';
import { useT } from '../i18n';
import { ShapeCircle, ShapeDiamond, ShapeWarn } from './icons';

export function Switch(props: { label: string; checked: boolean; onChange?: (v: boolean) => void; disabled?: boolean; help?: string; className?: string }) {
  const id = useId();
  return (
    <div className="reglage">
      <label className={`interrupteur ${props.disabled ? 'fixe' : ''} ${props.className ?? ''}`} htmlFor={id}>
        <input
          id={id}
          type="checkbox"
          role="switch"
          checked={props.checked}
          disabled={props.disabled}
          aria-describedby={props.help ? id + '-h' : undefined}
          onChange={(e) => props.onChange?.(e.target.checked)}
        />
        <span className="piste" aria-hidden />
        <span>{props.label}</span>
      </label>
      {props.help && <p className="aide" id={id + '-h'}>{props.help}</p>}
    </div>
  );
}

export function Segmented<V extends string>(props: { legend: string; value: V; options: { value: V; label: string }[]; onChange: (v: V) => void; hideLegend?: boolean }) {
  const name = useId();
  return (
    <fieldset className="segments">
      <legend className={props.hideLegend ? 'sr-only' : undefined}>{props.legend}</legend>
      {props.options.map((o) => (
        <label className="segment" key={o.value}>
          <input type="radio" name={name} value={o.value} checked={props.value === o.value} onChange={() => props.onChange(o.value)} />
          <span>{o.label}</span>
        </label>
      ))}
    </fieldset>
  );
}

export function Badge({ status }: { status: SegmentStatus }) {
  const { t } = useT();
  return (
    <span className={`badge ${status}`}>
      {status === 'validated' ? <ShapeCircle /> : status === 'machine' ? <ShapeDiamond /> : <ShapeWarn />}
      {t(`translate.badge.${status}`)}
    </span>
  );
}

export function StatusPill({ state, demo, autonomous }: { state: ServerState | 'loading'; demo?: boolean; autonomous?: boolean }) {
  const { t } = useT();
  if (state === 'loading') return <span className="etat offline" role="status">{t('states.loading')}</span>;
  return (
    <span className={`etat ${state}`} role="status" aria-live="polite">
      <i aria-hidden />
      {t(`status.${state}`)}
      {demo && state !== 'notConnected' && <small>· {t('status.demo')}</small>}
      {autonomous && state === 'ready' && <small>· {t('status.autonomous')}</small>}
    </span>
  );
}

/** Message bref qui disparaît seul. */
export function useToast(): [string | null, (m: string) => void] {
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    if (!msg) return;
    const id = setTimeout(() => setMsg(null), 2600);
    return () => clearTimeout(id);
  }, [msg]);
  return [msg, setMsg];
}

export function Toast({ msg }: { msg: string | null }) {
  return msg ? <div className="toast" role="status">{msg}</div> : null;
}
