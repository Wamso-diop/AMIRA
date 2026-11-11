/** Flèche tracée à la main et gribouillis (3 au total dans le panneau). */
export function HandArrow({ className = 'fleche' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 74 82" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M58 6c-14 2-30 10-33 24-3 13 9 18 15 10 6-9-6-17-16-9C14 39 12 58 20 74" />
      <path d="M10 64c3 4 7 8 10 11 3-5 6-9 9-12" />
    </svg>
  );
}

/** Gribouillis 1 : boucle (accueil). */
export function ScribbleLoop({ style }: { style?: React.CSSProperties }) {
  return (
    <svg className="gribouillis" style={style} width="120" height="46" viewBox="0 0 120 46" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" aria-hidden>
      <path d="M4 32c14-2 22-20 34-22 10-2 9 14-1 15-9 1-5-16 8-17 16-2 22 22 38 20 12-1 17-12 30-14" />
    </svg>
  );
}

/** Gribouillis 2 : soulignement nerveux (journal vide). */
export function ScribbleUnderline({ style }: { style?: React.CSSProperties }) {
  return (
    <svg className="gribouillis" style={style} width="150" height="18" viewBox="0 0 150 18" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" aria-hidden>
      <path d="M3 10c20-6 40-6 60-2 18 4 34 2 50-3 12-3 22-3 34 1" />
      <path d="M20 15c30-4 60-3 92-1" />
    </svg>
  );
}

/** Gribouillis 3 : étincelle (état « serveur non connecté »). */
export function ScribbleSpark({ style }: { style?: React.CSSProperties }) {
  return (
    <svg className="gribouillis" style={style} width="44" height="44" viewBox="0 0 44 44" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" aria-hidden>
      <path d="M22 4v10M22 30v10M4 22h10M30 22h10M10 10l6 6M28 28l6 6M34 10l-6 6M16 28l-6 6" />
    </svg>
  );
}
