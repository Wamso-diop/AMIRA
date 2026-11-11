/**
 * Les 4 pétales du logo = les langues. Pétale coloré = langue active, gris = bientôt.
 * Gouttes pointées vers le centre, disposées comme dans le symbole Amira.
 */
const PETAL = 'M0 -8 C 6 -13 7.5 -17 7.5 -21 A 7.5 7.5 0 0 0 -7.5 -21 C -7.5 -17 -6 -13 0 -8 Z';

export function Petals({ active = 0, size = 40, label }: { active?: number; size?: number; label?: string }) {
  const colors = ['var(--rose)', 'var(--vert)', 'var(--jaune)', 'var(--bleu)'];
  const angles = [15, -60, -125, 165];
  return (
    <svg className="petales" viewBox="-30 -30 60 60" width={size} height={size} role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      {angles.map((a, i) => (
        <path key={a} d={PETAL} transform={`rotate(${a})`} fill={i === active ? colors[i] : 'var(--gris-petale)'} />
      ))}
    </svg>
  );
}
