import { useEffect, useRef, useState, type CSSProperties } from 'react';
import logoClair from '../assets/amira-logo-clair.png';
import { useT } from './i18n';
import './onboarding.css';

/** Accueil au premier lancement : une vraie séquence de 3 écrans, chacun avec son animation. */
export function Onboarding({ onDone }: { onDone: () => void }) {
  const { t } = useT();
  const [step, setStep] = useState(0);
  const [dir, setDir] = useState<1 | -1>(1);
  const titleRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => titleRef.current?.focus(), [step]);
  const last = step === 2;
  const go = (n: number) => {
    setDir(n > step ? 1 : -1);
    setStep(n);
  };
  const words = t(`onboarding.s${step + 1}title`).split(' ');

  return (
    <div className="onb">
      <svg className="onb-fond" viewBox="-30 -30 60 60" aria-hidden>
        <path d="M0 -8 C 6 -13 7.5 -17 7.5 -21 A 7.5 7.5 0 0 0 -7.5 -21 C -7.5 -17 -6 -13 0 -8 Z" />
      </svg>

      <div className="onb-haut">
        <img className="onb-logo" src={logoClair} alt="Amira" />
        <button className="onb-passer" onClick={onDone}>{t('onboarding.skip')}</button>
      </div>

      <div className="onb-scene" key={step} data-dir={dir}>
        <div className="onb-illus" aria-hidden>
          {step === 0 && <Bloom />}
          {step === 1 && <MaskDemo />}
          {step === 2 && <DoubtDemo />}
        </div>
        <p className="onb-etape" aria-hidden>{step + 1} / 3</p>
        <h1 ref={titleRef} tabIndex={-1} className="onb-titre" aria-label={words.join(' ')}>
          {words.map((w, i) => (
            <span key={i}>
              <span className="onb-mot" style={{ '--i': i } as CSSProperties} aria-hidden>{w}</span>
              {i < words.length - 1 ? ' ' : ''}
            </span>
          ))}
        </h1>
        <p className="onb-texte">{t(`onboarding.s${step + 1}body`)}</p>
      </div>

      <div className="onb-actions">
        <div className="onb-points" role="group" aria-label={`${step + 1} / 3`}>
          {[0, 1, 2].map((i) => (
            <button key={i} data-on={i === step} aria-label={`${i + 1} / 3`} aria-current={i === step ? 'step' : undefined} onClick={() => go(i)} />
          ))}
        </div>
        <button className="onb-suivant" onClick={() => (last ? onDone() : go(step + 1))}>
          {last ? t('onboarding.start') : t('onboarding.next')}
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M5 12h13M13 6l6 6-6 6" />
          </svg>
        </button>
      </div>
    </div>
  );
}

const PETAL = 'M0 -8 C 6 -13 7.5 -17 7.5 -21 A 7.5 7.5 0 0 0 -7.5 -21 C -7.5 -17 -6 -13 0 -8 Z';

/** Écran 1 : les 4 pétales (les langues) éclosent ; le pétale du fulfulde reste actif. */
function Bloom() {
  const petals = [
    { a: 15, c: 'var(--rose)', on: true },
    { a: -60, c: 'var(--vert)' },
    { a: -125, c: 'var(--jaune)' },
    { a: 165, c: 'var(--bleu)' },
  ];
  return (
    <svg className="bloom" viewBox="-30 -30 60 60" width="150" height="150">
      {petals.map((p, i) => (
        <g key={p.a} transform={`rotate(${p.a})`}>
          <path className={`bloom-p ${p.on ? 'actif' : ''}`} d={PETAL} fill={p.c} style={{ '--d': `${i * 110}ms` } as CSSProperties} />
        </g>
      ))}
    </svg>
  );
}

/** Écran 2 : sur l'écran la vraie valeur ; vers le serveur, un marqueur. */
function MaskDemo() {
  const { t } = useT();
  return (
    <div className="masque">
      <div className="masque-ligne">
        <span className="masque-etiquette">{t('onboarding.s2screen')}</span>
        <p>
          {t('onboarding.s2a')} <b className="masque-val">50 000 FCFA</b> {t('onboarding.s2b')} <b className="masque-val">Jean Mbarga</b>
        </p>
      </div>
      <svg className="masque-lien" viewBox="0 0 40 34" aria-hidden>
        <path d="M20 2 C 8 10, 32 18, 20 30" />
        <path d="M14 25 L20 31 L26 25" />
      </svg>
      <div className="masque-ligne envoye">
        <span className="masque-etiquette">{t('onboarding.s2sent')}</span>
        <p>
          {t('onboarding.s2a')} <span className="masque-jeton" style={{ '--d': '900ms' } as CSSProperties}>{'{N0}'}</span> {t('onboarding.s2b')}{' '}
          <span className="masque-jeton" style={{ '--d': '1150ms' } as CSSProperties}>{'{N1}'}</span>
        </p>
      </div>
    </div>
  );
}

/** Écran 3 : un passage incertain garde l'original, signalé par ⚠ ; « Voir l'original » toujours là. */
function DoubtDemo() {
  const { t } = useT();
  return (
    <div className="doute">
      <p className="doute-ligne">
        <span className="doute-alerte">⚠</span>
        {t('onboarding.s3sample')}
      </p>
      <div className="doute-bas">
        <span className="doute-bouton">{t('translate.seeOriginal')}</span>
        <svg className="doute-fleche" viewBox="0 0 74 60" fill="none" aria-hidden>
          <path d="M70 6 C 52 4, 40 14, 44 26 C 48 38, 64 30, 56 22 C 46 12, 24 26, 10 40" />
          <path d="M8 28 L9 42 L22 43" />
        </svg>
      </div>
    </div>
  );
}
