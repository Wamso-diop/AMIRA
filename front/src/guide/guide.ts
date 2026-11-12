// Guide d'installation affiché par `npm run dev` : 7 diapositives animées.
import '@fontsource/inter-tight/latin-500.css';
import '@fontsource/inter-tight/latin-800.css';
import '@fontsource/inter-tight/latin-900.css';
import '@fontsource/noto-sans/latin-400.css';
import './guide.css';

const slides = [...document.querySelectorAll<HTMLElement>('.g-slide')];
const points = document.getElementById('points')!;
const prec = document.getElementById('prec') as HTMLButtonElement;
const suiv = document.getElementById('suiv') as HTMLButtonElement;
let courant = 0;

slides.forEach((s, i) => {
  const b = document.createElement('button');
  b.setAttribute('aria-label', `${i + 1}. ${s.dataset.titre}`);
  b.addEventListener('click', () => aller(i));
  points.appendChild(b);
});

function aller(i: number) {
  courant = Math.max(0, Math.min(slides.length - 1, i));
  slides.forEach((s, k) => {
    s.classList.remove('active');
    s.hidden = k !== courant;
  });
  const s = slides[courant];
  void s.offsetWidth; // relance les animations
  s.classList.add('active');
  [...points.children].forEach((p, k) => p.toggleAttribute('data-on', k === courant));
  prec.disabled = courant === 0;
  suiv.innerHTML = courant === slides.length - 1 ? 'Recommencer <span aria-hidden="true">↺</span>' : 'Suivant <span aria-hidden="true">→</span>';
  history.replaceState(null, '', `#${courant + 1}`);
}

prec.addEventListener('click', () => aller(courant - 1));
suiv.addEventListener('click', () => aller(courant === slides.length - 1 ? 0 : courant + 1));
document.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowRight') aller(courant + 1);
  if (e.key === 'ArrowLeft') aller(courant - 1);
});

document.addEventListener('click', async (e) => {
  const b = (e.target as Element).closest<HTMLButtonElement>('.g-copier');
  if (!b) return;
  const texte = b.dataset.copier!;
  try {
    await navigator.clipboard.writeText(texte);
    b.textContent = 'Copié';
    setTimeout(() => (b.textContent = 'Copier'), 1600);
  } catch {
    b.textContent = 'Sélectionnez le texte';
  }
});

aller(Math.max(0, Number(location.hash.slice(1)) - 1 || 0));
window.addEventListener('hashchange', () => {
  const n = Number(location.hash.slice(1)) - 1;
  if (n >= 0 && n !== courant) aller(n);
});
