/** Icônes en trait, dessinées pour Amira (pas de bibliothèque tierce). */
type P = { title?: string };
const S = ({ children, title }: P & { children: React.ReactNode }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden={title ? undefined : true} role={title ? 'img' : undefined}>
    {title && <title>{title}</title>}
    {children}
  </svg>
);
export const IconCopy = (p: P) => <S {...p}><rect x="8" y="8" width="12" height="12" rx="1" /><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3" /></S>;
export const IconListen = (p: P) => <S {...p}><path d="M4 9v6h4l5 4V5L8 9H4z" /><path d="M16.5 8.5a5 5 0 0 1 0 7" /><path d="M19 6a8.5 8.5 0 0 1 0 12" /></S>;
export const IconSwap = (p: P) => <S {...p}><path d="M7 4v16" /><path d="M3 8l4-4 4 4" /><path d="M17 20V4" /><path d="M13 16l4 4 4-4" /></S>;
export const IconPlay = (p: P) => <S {...p}><path d="M7 4.5v15l12-7.5z" fill="currentColor" /></S>;
export const IconPause = (p: P) => <S {...p}><path d="M8 5v14M16 5v14" /></S>;
export const IconStop = (p: P) => <S {...p}><rect x="6" y="6" width="12" height="12" fill="currentColor" /></S>;
export const IconMic = (p: P) => <S {...p}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></S>;
export const IconLock = (p: P) => <S {...p}><rect x="5" y="11" width="14" height="10" rx="1" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></S>;
export const IconCheck = (p: P) => <S {...p}><path d="M4 12.5l5 5L20 6.5" /></S>;
export const IconCross = (p: P) => <S {...p}><path d="M6 6l12 12M18 6L6 18" /></S>;
export const IconRetry = (p: P) => <S {...p}><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 4v7h-7" /></S>;
export const IconDownload = (p: P) => <S {...p}><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></S>;
export const IconTrash = (p: P) => <S {...p}><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></S>;
export const IconEye = (p: P) => <S {...p}><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></S>;
export const IconFlag = (p: P) => <S {...p}><path d="M5 21V4M5 4h11l-2 4 2 4H5" /></S>;

/** Formes des badges : cercle (validée), losange (automatique), triangle (à vérifier). */
export const ShapeCircle = () => <svg viewBox="0 0 12 12" aria-hidden><circle cx="6" cy="6" r="5" fill="currentColor" /></svg>;
export const ShapeDiamond = () => <svg viewBox="0 0 12 12" aria-hidden><path d="M6 0.5L11.5 6 6 11.5 0.5 6z" fill="currentColor" /></svg>;
export const ShapeWarn = () => <svg viewBox="0 0 12 12" aria-hidden><path d="M6 0.8L11.5 11H0.5z" fill="currentColor" /><path d="M6 4.3v3.2M6 9.1v.3" stroke="#C2134C" strokeWidth="1.5" strokeLinecap="round" /></svg>;
export const IconTarget = (p: P) => <S {...p}><circle cx="12" cy="12" r="7.5" /><path d="M12 1.5v5M12 17.5v5M1.5 12h5M17.5 12h5" /><circle cx="12" cy="12" r="1.6" fill="currentColor" /></S>;
export const IconPage = (p: P) => <S {...p}><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4M9 12h6M9 16h6" /></S>;
export const IconAlert = (p: P) => <S {...p}><path d="M3 10v4h3l7 5V5L6 10H3z" /><path d="M17 9l3-2M17 15l3 2M18 12h3" /></S>;
