// Guide d'installation : 9 diapositives animées. Servi par le serveur Amira (/guide/, ouvert par `python demo.py`)
// et par `npm run dev`. La page n'écrit jamais dans le DOM autre chose que du texte (textContent).
import './fonts.css';
import './guide.css';
import './demo.css';

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

// Dossier de l'extension : `python demo.py` ouvre le guide avec ?dossier=<chemin complet> (sur cette machine seulement).
const dossier = new URLSearchParams(location.search).get('dossier');
if (dossier) document.querySelectorAll('[data-dossier]').forEach((el) => (el.textContent = dossier));

document.addEventListener('click', async (e) => {
  const b = (e.target as Element).closest<HTMLButtonElement>('.g-copier');
  if (!b) return;
  const libelle = b.textContent;
  const texte = 'copierDossier' in b.dataset ? dossier ?? 'extension' : b.dataset.copier!;
  try {
    await navigator.clipboard.writeText(texte);
    b.textContent = 'Copié';
    setTimeout(() => (b.textContent = libelle), 1600);
  } catch {
    b.textContent = 'Sélectionnez le texte';
  }
});

aller(Math.max(0, Number(location.hash.slice(1)) - 1 || 0));
window.addEventListener('hashchange', () => {
  const n = Number(location.hash.slice(1)) - 1;
  if (n >= 0 && n !== courant) aller(n);
});

// Pastille d'en-tête : état réel du serveur qui sert ce guide (/v1/ready : 200 prêt, 503 modèle en chargement).
const statut = document.getElementById('statut')!;
const libelle = statut.querySelector('span')!;
async function verifier() {
  try {
    const r = await fetch('/v1/ready', { cache: 'no-store' });
    statut.dataset.etat = r.ok ? 'pret' : 'charge';
    libelle.textContent = r.ok ? 'Serveur Amira prêt' : 'Serveur Amira lancé : le modèle de traduction se charge…';
    setTimeout(verifier, r.ok ? 10000 : 2000);
  } catch {
    statut.dataset.etat = 'absent';
    libelle.textContent = 'Serveur Amira non joint : lancez python demo.py';
    setTimeout(verifier, 5000);
  }
}
verifier();
if (import.meta.env.DEV) document.getElementById('pied-dev')!.hidden = false;
