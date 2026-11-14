// Figures du dossier livrable, dessinées dans la charte Amira : aubergine #481C4B, rose #E01D5B, jaune #EFD109, vert #2DCF42, bleu #2BB1EB ;
// Inter Tight (titres) et Noto Sans (texte) ; coins en biseau ; ni ombres ni dégradés ; les pétales indiquent les langues.
// Les captures utilisées viennent de scripts/livrable-capture.mjs (vraie extension, vrai serveur).
// Usage (depuis front/) : node scripts/livrable-figures.mjs  → docs/figures/*.png
import { chromium } from '@playwright/test';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const AUB = '#481C4B', ROSE = '#E01D5B', JAUNE = '#EFD109', VERT = '#2DCF42', BLEU = '#2BB1EB', DOUX = '#F7F2F7', CLAIR = '#FBF3FA', GRIS = '#D9CBDA';
const FIG = 'docs/figures';
const b64 = (p) => `data:image/png;base64,${readFileSync(resolve(p)).toString('base64')}`;
const dims = (p) => { const d = readFileSync(resolve(p)); return [d.readUInt32BE(16), d.readUInt32BE(20)]; };
const boxes = existsSync(`${FIG}/boxes.json`) ? JSON.parse(readFileSync(`${FIG}/boxes.json`, 'utf8')) : {};

// polices intégrées en base64 : une page injectée (setContent) ne peut pas lire de fichier local
const f = (slug, sub, w) => `data:font/woff2;base64,${readFileSync(resolve(`node_modules/@fontsource/${slug}/files/${slug}-${sub}-${w}-normal.woff2`)).toString('base64')}`;
const faces = [['Inter Tight', 'inter-tight', [800, 900]], ['Noto Sans', 'noto-sans', [400, 700]]]
  .flatMap(([fam, slug, ws]) => ws.flatMap((w) => ['latin', 'latin-ext'].map((sub) =>
    `@font-face{font-family:'${fam}';font-weight:${w};src:url('${f(slug, sub, w)}') format('woff2');unicode-range:${sub === 'latin' ? 'U+0000-00FF,U+0131,U+2000-206F,U+20AC,U+2122,U+2190-2193,U+2212,U+25A0-25FF,U+2713,U+2717,U+26A0' : 'U+0100-02BA,U+1E00-1EFF'}}`))).join('\n');

const css = `${faces}
:root{--aub:${AUB};--rose:${ROSE};--jaune:${JAUNE};--vert:${VERT};--bleu:${BLEU};--doux:${DOUX};--clair:${CLAIR}}
*{box-sizing:border-box}body{margin:0;background:#fff;font:400 22px/1.4 'Noto Sans',sans-serif;color:var(--aub)}
h1,h2,h3,h4{font-family:'Inter Tight',sans-serif;font-weight:900;margin:0;letter-spacing:-.015em;line-height:1.02}
.bev{clip-path:polygon(0 0,calc(100% - 20px) 0,100% 20px,100% 100%,20px 100%,0 calc(100% - 20px))}
.bev-s{clip-path:polygon(0 0,calc(100% - 12px) 0,100% 12px,100% 100%,12px 100%,0 calc(100% - 12px))}
.t{font-family:'Inter Tight',sans-serif;font-weight:900}
.mono{font:700 .86em ui-monospace,'DejaVu Sans Mono',monospace}
.chip{display:inline-block;font:700 19px 'Noto Sans',sans-serif;padding:3px 14px}
.kw{display:inline-block;background:var(--jaune);color:var(--aub);padding:0 .18em;transform:rotate(-1.6deg)}
.pin{display:inline-grid;place-items:center;width:46px;height:46px;border-radius:50%;background:var(--rose);color:#fff;font:900 26px 'Inter Tight',sans-serif}
.win{background:#fff;border:5px solid var(--aub)}
.win .bar{background:var(--aub);height:44px;display:flex;align-items:center;gap:8px;padding:0 16px}
.win .bar i{width:12px;height:12px;border-radius:50%;background:var(--clair);opacity:.55}
.win .bar span{margin-left:14px;background:var(--clair);color:var(--aub);font:700 16px 'Noto Sans',sans-serif;padding:3px 16px;border-radius:99px}
`;

const petal = (c, r) => `<g transform="rotate(${r}) scale(1.45)"><path d="M0 -6 C 5 -11 6.5 -15 6.5 -19 A 6.5 6.5 0 0 0 -6.5 -19 C -6.5 -15 -5 -11 0 -6 Z" fill="${c}"/></g>`;
const flower = (size, colors = [ROSE, VERT, JAUNE, BLEU]) => `<svg viewBox="-34 -34 68 68" width="${size}" height="${size}">${[12, -48, -132, 168].map((r, i) => petal(colors[i], r)).join('')}</svg>`;
const arrow = (w = 190, color = ROSE) => `<svg viewBox="0 0 190 120" width="${w}" fill="none" stroke="${color}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"><path d="M10 20 C 70 -6, 150 22, 168 96"/><path d="M142 78 L 168 100 L 176 66"/></svg>`;
const crop = (src, [iw], x, y, w, h, s) => `<div style="width:${w * s}px;height:${h * s}px;overflow:hidden;position:relative"><img src="${src}" style="position:absolute;left:${-x * s}px;top:${-y * s}px;width:${iw * s}px;display:block"></div>`;

const real = (n) => ({ src: b64(`${FIG}/real-${n}.png`), d: dims(`${FIG}/real-${n}.png`) });
const pan = { traduire: real('panneau-traduire'), voix: real('panneau-voix') };
const cropPanel = (tab, ycss, hcss, width) => { const p = pan[tab]; return crop(p.src, p.d, 0, ycss * 2, 800, hcss * 2, width / 800); };

const figures = {};

// ------------------------------------------------------------------ COUVERTURE (A4, plein cadre)
figures.cover = { w: 1654, h: 2339, scale: 1, html: `
<div style="position:relative;width:1654px;height:2339px;background:${AUB};color:${CLAIR};overflow:hidden">
 <img src="${b64('src/assets/amira-logo-clair.png')}" style="position:absolute;left:120px;top:110px;height:92px">
 <div style="position:absolute;left:120px;top:470px;width:1000px">
  <div class="t" style="font-size:36px;color:${JAUNE};margin-bottom:34px">Livrable remis au jury</div>
  <h1 style="font-size:168px;line-height:.98;white-space:nowrap">Dossier de<br><span class="kw" style="margin-top:14px;background:${JAUNE}">candidature</span></h1>
  <p class="t" style="font-weight:800;font-size:46px;line-height:1.22;margin:84px 0 0;max-width:880px;letter-spacing:-.01em">Amira rend les services financiers numériques compréhensibles en fulfulde, sans modifier le service.</p>
  <p class="t" style="font-size:44px;color:${JAUNE};margin:46px 0 0">Lire. Comprendre. Agir.</p>
 </div>
 <div style="position:absolute;left:1030px;top:640px">${arrow(210, JAUNE)}</div>
 <div class="bev" style="position:absolute;left:1075px;top:1010px;width:470px;height:880px;background:${CLAIR};padding:14px">
  <div style="width:442px;height:852px;overflow:hidden;background:#fff">${crop(pan.traduire.src, pan.traduire.d, 0, 0, 800, 1500, 442 / 800)}</div>
 </div>
 <div style="position:absolute;left:120px;top:1810px;display:flex;align-items:center;gap:40px">
  ${flower(210)}
  <div style="max-width:560px"><div class="t" style="font-size:36px;color:${JAUNE}">Fulfulde aujourd'hui</div><div style="font-size:27px;margin-top:8px;opacity:.92">Les autres langues nationales viendront une à une, un dossier à la fois.</div></div>
 </div>
 <div style="position:absolute;left:120px;right:120px;bottom:110px;border-top:5px solid ${JAUNE};padding-top:30px;display:flex;justify-content:space-between;align-items:flex-end">
  <div><div class="t" style="font-size:34px;color:${JAUNE}">SAFINUM Innovate Challenge</div><div style="font-size:26px;margin-top:6px">Épreuve de présélection du hackathon</div></div>
  <div style="font:700 26px 'Noto Sans';text-align:right">Équipe Amira<br><span style="font-weight:400">Novembre 2026 · Version 1.0</span></div>
 </div>
</div>` };

// ------------------------------------------------------------------ BANDEAUX DE SECTION (17 cm x 3,6 cm)
const sections = [
  ['01', 'Ce que fait Amira, pour qui, et ce que le jury peut vérifier', ROSE],
  ['02', 'Lancer, installer, tester : cinq minutes, une commande', VERT],
  ['03', 'Comment c\'est construit, comment ça s\'intègre, où sont les limites', BLEU],
  ['04', 'Une langue validée par des locuteurs natifs, jamais inventée', JAUNE],
  ['05', 'Ce que nous avons construit, ce que nous avons réutilisé', ROSE],
  ['06', 'Configurer, intégrer chez un opérateur, ajouter une langue', VERT],
  ['07', 'Une langue de plus, un dossier de plus', BLEU],
];
sections.forEach(([n, chapo, c], i) => {
  figures[`banner-${i + 1}`] = { w: 1700, h: 310, scale: 1.5, html: `
  <div class="bev" style="width:1700px;height:310px;background:${AUB};position:relative;color:${CLAIR};overflow:hidden">
   <div class="t" style="position:absolute;left:54px;top:-18px;font-size:300px;line-height:1;color:${JAUNE};letter-spacing:-.04em">${n}</div>
   <div style="position:absolute;left:470px;top:62px;width:860px"><div class="t" style="font-size:25px;color:${c};letter-spacing:.01em">Section ${i + 1} sur 7</div><div class="t" style="font-weight:800;font-size:46px;line-height:1.12;margin-top:14px">${chapo}</div></div>
   <div style="position:absolute;right:58px;top:50px">${flower(210)}</div>
   <div style="position:absolute;left:0;right:0;bottom:0;height:16px;background:${c}"></div>
  </div>` };
});

// ------------------------------------------------------------------ 1. Avant / après (captures réelles)
const avant = real('avant'), apres = real('apres');
const WV = 700;
const view = (img, hnative, label, extra = '') => `<div style="width:${WV + 10}px"><div class="win"><div class="bar"><i></i><i></i><i></i><span>banque-demo.exemple</span></div>
  <div style="position:relative;width:${WV}px;height:${Math.round(hnative * WV / 2360)}px;overflow:hidden"><img src="${img.src}" style="width:${WV}px;display:block">${extra}</div></div>
  <div class="t" style="font-size:30px;margin-top:14px;text-align:center">${label}</div></div>`;
const ov = (x, y, w, h, color = ROSE) => `<div style="position:absolute;left:${x * WV / 2360}px;top:${y * WV / 2360}px;width:${w * WV / 2360}px;height:${h * WV / 2360}px;border:6px solid ${color};border-radius:10px"></div>`;
figures.hero = { w: 1700, h: 700, scale: 1.5, html: `
<div style="width:1700px;padding:26px;background:#fff;display:grid;grid-template-columns:${WV + 10}px 1fr ${WV + 10}px;align-items:start">
 ${view(avant, 1450, 'Avant : la page, telle qu\'elle est')}
 <div style="padding-top:170px;text-align:center"><div class="bev-s" style="display:inline-block;background:${JAUNE};padding:14px 22px;font:900 28px 'Inter Tight',sans-serif;line-height:1.1">Un clic<br>sur Traduire</div><div style="margin-top:6px">${arrow(120)}</div></div>
 ${view(apres, 1450, 'Après : tout est en fulfulde', ov(228, 405, 530, 100) + ov(228, 530, 640, 100) + `<div class="bev-s" style="position:absolute;left:${230 * WV / 2360}px;top:${640 * WV / 2360}px;background:${ROSE};color:#fff;padding:2px 12px;font:700 17px 'Noto Sans'">montant identique</div>`)}
</div>` };

// ------------------------------------------------------------------ 2. Le panneau en quatre gestes (détails réels)
const card = (n, titre, texte, img, color) => `<div style="width:830px;background:${DOUX};padding:0 0 24px" class="bev">
  <div style="background:${color};padding:14px 22px;display:flex;align-items:center;gap:16px"><span class="pin" style="background:${AUB}">${n}</span><span class="t" style="font-size:34px;color:${color === ROSE || color === AUB ? '#fff' : AUB}">${titre}</span></div>
  <div style="padding:20px 24px 0"><div style="border:4px solid ${AUB};background:#fff;overflow:hidden">${img}</div><p style="margin:16px 0 0;font-size:22px">${texte}</p></div></div>`;
figures.gestes = { w: 1700, h: 1290, scale: 1.5, html: `
<div style="width:1700px;padding:24px;background:#fff;display:grid;grid-template-columns:830px 830px;gap:26px">
 ${card(1, 'Traduire en un clic', 'Un gros bouton rond. Les compteurs disent ce qui est traduit, gardé en français, en erreur.', cropPanel('traduire', 410, 305, 780), JAUNE)}
 ${card(2, 'Écouter', 'La voix d\'un locuteur natif, étiquetée « Voix enregistrée ». Lecture de la page, d\'une sélection, ou des seuls messages.', cropPanel('voix', 498, 345, 780), VERT)}
 ${card(3, 'Savoir à qui se fier', 'Trois badges de forme différente : validée par un natif, automatique, à vérifier (l\'original reste).', cropPanel('traduire', 1290, 175, 780), BLEU)}
 ${card(4, 'Lire les erreurs, tout seul', 'Réglage actif par défaut : un message d\'erreur qui apparaît est traduit puis lu à voix haute.', cropPanel('voix', 930, 130, 780), ROSE)}
</div>` };

// ------------------------------------------------------------------ 3. Une erreur apparaît (page réelle + panneau)
const err = real('erreur');
figures.erreur = { w: 1700, h: 720, scale: 1.5, html: `
<div style="width:1700px;padding:26px;background:#fff;display:flex;gap:34px;align-items:stretch">
 <div style="flex:1"><div class="win"><div class="bar"><i></i><i></i><i></i><span>banque-demo.exemple</span></div>
  <div style="width:1000px;height:230px;overflow:hidden;position:relative">${crop(err.src, err.d, 0, 1330, 2360, 545, 1000 / 2360)}</div></div>
  <div class="t" style="font-size:28px;margin-top:14px">1. Une erreur apparaît après coup</div>
  <p style="margin:6px 0 0;font-size:21px">Amira la repère, la masque, la traduit : le message est traduit en quelques secondes.</p></div>
 <div style="width:560px"><div class="bev" style="background:${DOUX};padding:16px"><div style="border:4px solid ${AUB};background:#fff;overflow:hidden">${cropPanel('voix', 498, 345, 520)}</div></div>
  <div class="t" style="font-size:28px;margin-top:14px">2. Elle est lue à voix haute</div>
  <p style="margin:6px 0 0;font-size:21px">Avec l'enregistrement d'un locuteur natif, étiqueté « Voix enregistrée ».</p></div>
</div>` };

// ------------------------------------------------------------------ 4. Chiffres clés
const tile = (big, label, bg, fg = AUB) => `<div class="bev" style="background:${bg};color:${fg};padding:22px 24px 20px"><div class="t" style="font-size:78px;line-height:1">${big}</div><div style="font:700 21px/1.25 'Noto Sans';margin-top:10px">${label}</div></div>`;
figures.chiffres = { w: 1700, h: 250, scale: 1.5, html: `
<div style="width:1700px;padding:20px 24px;background:#fff;display:grid;grid-template-columns:repeat(5,1fr);gap:18px">
 ${tile('189', 'lignes validées par un locuteur natif', AUB, CLAIR)}
 ${tile('183', 'lignes avec la voix d\'un natif (sur 189)', JAUNE)}
 ${tile('539', 'tests automatisés, dont 8 dans un vrai navigateur', VERT)}
 ${tile('6,2 s', 'p95, page de 40 passages, sans carte graphique', BLEU)}
 ${tile('0', 'connexion sortante du serveur', ROSE, '#fff')}
</div>` };

// ------------------------------------------------------------------ 5. Architecture
const node = (titre, texte, bg, fg = AUB, extra = '') => `<div class="bev" style="background:${bg};color:${fg};padding:20px 24px;${extra}"><div class="t" style="font-size:30px">${titre}</div><div style="font-size:21px;margin-top:6px;line-height:1.3">${texte}</div></div>`;
figures.architecture = { w: 1700, h: 800, scale: 1.5, html: `
<div style="width:1700px;padding:26px;background:#fff;display:grid;grid-template-columns:1fr 200px 460px;align-items:stretch">
 <div class="bev" style="border:0;background:${DOUX};padding:22px 24px">
  <div class="t" style="font-size:32px;margin-bottom:16px">Navigateur Chrome</div>
  <div style="display:grid;grid-template-columns:330px 1fr;gap:18px">
   ${node('Page du service', 'Inchangée : aucun code à modifier. Lue, jamais modifiée dans sa source.', '#fff', AUB, `border:4px solid ${AUB};`)}
   <div style="display:grid;gap:14px">
    ${node('Script de contenu', 'découpage en passages · <b>masquage local</b> · vérification · observation en direct', JAUNE)}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">${node('Panneau latéral', 'Traduire · Voix · Réglages · Journal', AUB, CLAIR)}${node('Service worker', 'cache · nouvelles tentatives · journal sans données', AUB, CLAIR)}</div>
   </div></div>
  <div style="margin-top:20px;font:700 23px 'Noto Sans'"><span class="chip" style="background:${ROSE};color:#fff">Seul le texte masqué quitte le navigateur</span></div>
 </div>
 <div style="display:flex;flex-direction:column;justify-content:center;align-items:center;gap:8px"><div class="t" style="font-size:54px;color:${ROSE};line-height:1">→</div><div class="mono" style="font-size:19px;text-align:center;line-height:1.5">/v1/translate<br>/v1/tts<br>/v1/feedback</div></div>
 <div class="bev" style="background:${AUB};color:${CLAIR};padding:22px 26px">
  <div style="display:flex;align-items:center;gap:14px"><div class="t" style="font-size:34px;color:${JAUNE}">API Amira</div><span class="chip" style="background:${JAUNE};color:${AUB}">Flask</span></div>
  <div style="margin-top:16px;font:700 23px 'Noto Sans';line-height:1.5">garde <span style="color:${JAUNE}">→</span> mémoire validée <span style="color:${JAUNE}">→</span> modèle</div>
  <div class="bev-s" style="margin-top:18px;background:${CLAIR};color:${AUB};padding:16px 20px"><div class="t" style="font-size:26px">Une langue = un dossier</div><div class="mono" style="font-size:19px;margin-top:6px">languages/&lt;code&gt;/</div><div style="font-size:19px;margin-top:4px">fiche · mémoire validée · voix</div></div>
  <div style="margin-top:16px;font-size:20px;opacity:.9">SQLite · aucun service externe</div>
 </div>
</div>` };

// ------------------------------------------------------------------ 6. Masquage
figures.masquage = { w: 1700, h: 520, scale: 1.5, html: `
<div style="width:1700px;padding:26px;background:#fff;display:grid;grid-template-columns:1fr 54px 1fr 54px 1fr 54px 1fr;align-items:stretch">
 ${node('Sur la page', 'Votre solde est de <b>250 000 FCFA</b> au <b>11/11/2026</b>.', DOUX)}<div class="t" style="font-size:46px;color:${ROSE};align-self:center;text-align:center">→</div>
 <div class="bev" style="background:${JAUNE};padding:20px 24px"><div class="t" style="font-size:30px">Masqué ici</div><div style="font-size:21px;margin-top:6px">Votre solde est de <span class="mono" style="background:#fff;padding:0 6px">{N0}</span> au <span class="mono" style="background:#fff;padding:0 6px">{N1}</span>.</div><div class="chip" style="background:${AUB};color:${CLAIR};margin-top:14px">seul ce texte voyage</div></div><div class="t" style="font-size:46px;color:${ROSE};align-self:center;text-align:center">→</div>
 ${node('Traduit par le serveur', '… <span class="mono" style="background:#fff;color:' + AUB + ';padding:0 6px">{N0}</span> … <span class="mono" style="background:#fff;color:' + AUB + ';padding:0 6px">{N1}</span> …<br><span style="color:' + JAUNE + '">garde · mémoire · modèle</span>', AUB, CLAIR)}<div class="t" style="font-size:46px;color:${ROSE};align-self:center;text-align:center">→</div>
 <div style="display:grid;gap:12px">
  ${node('Vérifié ici', 'chaque marqueur présent, <b>une seule fois</b> ?', DOUX)}
  <div class="bev-s" style="background:${VERT};padding:12px 18px;font:700 21px 'Noto Sans'"><b>Oui</b> : valeurs remises, traduction affichée</div>
  <div class="bev-s" style="background:${ROSE};color:#fff;padding:12px 18px;font:700 21px 'Noto Sans'"><b>Non</b> : l'original reste, avec ⚠</div>
 </div>
</div>` };

// ------------------------------------------------------------------ 7. Le serveur décide en six étapes
const step = (n, titre, texte, res, resBg, resFg = AUB) => `<div style="display:flex;flex-direction:column;gap:12px"><div class="bev-s" style="background:${DOUX};padding:16px 16px 18px;flex:1"><span class="pin" style="width:42px;height:42px;font-size:23px">${n}</span><div class="t" style="font-size:25px;margin-top:10px">${titre}</div><div style="font-size:18px;margin-top:6px;line-height:1.3">${texte}</div></div><div class="bev-s chip" style="background:${resBg};color:${resFg};text-align:center;padding:8px 6px">${res}</div></div>`;
figures.pipeline = { w: 1700, h: 470, scale: 1.5, html: `
<div style="width:1700px;padding:26px;background:#fff">
 <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:16px">
  ${step(1, 'Garde', 'Refuse tout chiffre, devise, e-mail ou IBAN restant', 'uncertain', ROSE, '#fff')}
  ${step(2, 'Mémoire validée', 'La traduction relue par un locuteur natif', 'validated', VERT)}
  ${step(3, 'Catégorie sensible', 'Frais ou avertissement sans version validée : pas de modèle', 'uncertain', ROSE, '#fff')}
  ${step(4, 'Cache machine', 'Mémoire vive, texte masqué seulement', 'machine', JAUNE)}
  ${step(5, 'Modèle', 'Sous contrôle : budget de 6 s, erreurs d\'abord', 'machine', JAUNE)}
  ${step(6, 'Contrôle', 'Marqueurs vérifiés, ici puis sur la page', 'sinon uncertain', ROSE, '#fff')}
 </div>
 <div style="margin-top:18px;font:700 23px 'Noto Sans'"><span style="color:${ROSE}">→</span> Un texte s'arrête à la première étape qui décide. <span style="font-weight:400">En cas de doute, l'original reste affiché.</span></div>
</div>` };

// ------------------------------------------------------------------ 8. Statuts (formes différentes en plus des couleurs)
figures.statuts = { w: 1700, h: 330, scale: 1.5, html: `
<div style="width:1700px;padding:26px;background:#fff;display:grid;grid-template-columns:repeat(3,1fr);gap:20px">
 <div class="bev" style="background:${DOUX};padding:24px"><div style="display:flex;align-items:center;gap:16px"><svg width="58" height="58"><circle cx="29" cy="29" r="26" fill="${VERT}"/><circle cx="29" cy="29" r="9" fill="${AUB}"/></svg><div class="t" style="font-size:38px">Validée</div></div><p style="margin:12px 0 0;font-size:22px">Relue par un locuteur natif. C'est la seule source dite validée.</p></div>
 <div class="bev" style="background:${DOUX};padding:24px"><div style="display:flex;align-items:center;gap:16px"><svg width="58" height="58"><path d="M29 3 L55 29 L29 55 L3 29 Z" fill="${JAUNE}"/><path d="M29 20 L38 29 L29 38 L20 29 Z" fill="${AUB}"/></svg><div class="t" style="font-size:38px">Automatique</div></div><p style="margin:12px 0 0;font-size:22px">Produite par le modèle, non relue. Jamais présentée comme validée.</p></div>
 <div class="bev" style="background:${DOUX};padding:24px"><div style="display:flex;align-items:center;gap:16px"><svg width="58" height="58"><path d="M29 4 L56 52 L2 52 Z" fill="${ROSE}"/><rect x="26" y="20" width="6" height="18" fill="#fff"/><rect x="26" y="42" width="6" height="6" fill="#fff"/></svg><div class="t" style="font-size:38px">À vérifier</div></div><p style="margin:12px 0 0;font-size:22px">Un doute : <b>l'original reste affiché</b>.</p></div>
</div>` };

// ------------------------------------------------------------------ 9. Circuit de validation
const flow = (titre, texte, bg, fg = AUB, w = '') => `<div class="bev" style="background:${bg};color:${fg};padding:18px 22px;${w}"><div class="t" style="font-size:27px">${titre}</div><div style="font-size:20px;margin-top:4px;line-height:1.3">${texte}</div></div>`;
figures.validation = { w: 1700, h: 640, scale: 1.5, html: `
<div style="width:1700px;padding:26px;background:#fff;position:relative">
 <div style="display:grid;grid-template-columns:360px 60px 560px 60px 1fr;align-items:center;row-gap:22px">
  ${flow('Texte à traduire', 'masqué, envoyé au serveur', DOUX)}<div class="t" style="font-size:44px;color:${ROSE};text-align:center">→</div>
  <div style="display:grid;gap:16px">
   ${flow('Connu de la mémoire', 'affiché <b>Validée</b> (cercle)', VERT)}
   ${flow('Inconnu, courant (libellé, erreur)', 'le modèle propose : <b>Automatique</b> (losange), ou l\'original reste', JAUNE)}
   ${flow('Inconnu et sensible (frais, sécurité)', '<b>pas de modèle</b> : l\'original reste, texte noté à valider', ROSE, '#fff')}
  </div><div class="t" style="font-size:44px;color:${ROSE};text-align:center">→</div>
  <div style="display:grid;gap:16px">
   ${flow('Le locuteur natif valide', 'par le fichier de mémoire ou les outils d\'administration', AUB, CLAIR)}
   ${flow('Validée pour tous', 'chaque utilisateur voit désormais la version relue', VERT)}
  </div>
 </div>
 <div class="bev-s" style="margin-top:26px;background:${DOUX};padding:16px 24px;display:flex;align-items:center;gap:22px"><span class="chip" style="background:${AUB};color:${CLAIR}">Boucle d'amélioration</span><span style="font-size:22px">L'utilisateur <b>signale</b> une traduction depuis l'onglet Journal (texte masqué) <span style="color:${ROSE};font-weight:900">→</span> un natif l'examine <span style="color:${ROSE};font-weight:900">→</span> elle devient validée.</span></div>
</div>` };

// ------------------------------------------------------------------ 10. Déploiement chez un opérateur
figures.deploiement = { w: 1700, h: 560, scale: 1.5, html: `
<div style="width:1700px;padding:26px;background:#fff;display:grid;grid-template-columns:340px 70px 360px 70px 1fr;align-items:center">
 ${node('Utilisateur', 'Chrome + extension Amira, installée depuis la boutique ou par l\'opérateur', DOUX)}
 <div class="t" style="font-size:44px;color:${ROSE};text-align:center">→</div>
 ${node('Passerelle de l\'opérateur', 'TLS · authentification · quotas ; <span class="mono">AMIRA_ALLOWED_ORIGINS</span>', JAUNE)}
 <div class="t" style="font-size:44px;color:${ROSE};text-align:center">→</div>
 <div class="bev" style="background:${AUB};color:${CLAIR};padding:20px 26px;position:relative"><div style="display:flex;gap:14px;align-items:center"><div class="t" style="font-size:32px;color:${JAUNE}">Serveur Amira</div><span class="chip" style="background:${JAUNE};color:${AUB}">réseau interne</span></div>
  <div style="font-size:21px;margin-top:8px">Flask · SQLite · modèle M2M100 · mémoire validée et voix</div>
  <div style="display:flex;gap:12px;margin-top:16px;flex-wrap:wrap"><span class="chip" style="background:${CLAIR};color:${AUB}">/v1/health</span><span class="chip" style="background:${CLAIR};color:${AUB}">/v1/ready</span><span class="chip" style="background:${ROSE};color:#fff">aucune connexion sortante</span></div></div>
</div>
<div style="width:1700px;padding:0 26px 26px;display:flex;gap:26px">
 <div class="bev-s" style="flex:1;background:${DOUX};padding:16px 22px"><span class="t" style="font-size:25px">Appel serveur à serveur</span><div style="font-size:20px;margin-top:4px">Un serveur de l'opérateur appelle l'API avec <span class="mono">X-Amira-Key</span>, en appliquant les mêmes règles de masquage.</div></div>
 <div class="bev-s" style="flex:1;background:${DOUX};padding:16px 22px"><span class="t" style="font-size:25px">Locuteurs natifs</span><div style="font-size:20px;margin-top:4px">Outils d'administration : jeton, réseau interne, chaque écriture auditée.</div></div>
</div>` };

// ------------------------------------------------------------------ 11. Performances
const bar = (label, med, p95) => `<div style="display:grid;grid-template-columns:420px 1fr;align-items:center;margin:14px 0"><div style="font:700 22px 'Noto Sans'">${label}</div>
 <div style="position:relative;height:56px"><div style="position:absolute;left:0;top:4px;height:22px;width:${med / 8 * 100}%;background:${AUB}"></div><span style="position:absolute;left:calc(${med / 8 * 100}% + 8px);top:0;font:700 19px 'Noto Sans'">${String(med).replace('.', ',')} s</span>
 <div style="position:absolute;left:0;top:30px;height:18px;width:${p95 / 8 * 100}%;background:${ROSE}"></div><span style="position:absolute;left:calc(${p95 / 8 * 100}% + 8px);top:25px;font:700 19px 'Noto Sans';color:${ROSE}">${String(p95).replace('.', ',')} s</span></div></div>`;
figures.perf = { w: 1700, h: 560, scale: 1.5, html: `
<div style="width:1700px;padding:26px 40px;background:#fff">
 <div style="display:flex;gap:34px;align-items:center;margin-bottom:10px"><span class="chip" style="background:${AUB};color:${CLAIR}">■ médiane</span><span class="chip" style="background:${ROSE};color:#fff">■ p95</span><span style="font-size:20px">Requêtes complètes, cache vide, processeur seul, 10 essais</span></div>
 <div style="position:relative">
  ${bar('1 segment inconnu', 1.9, 1.9)}${bar('8 segments inconnus', 5.7, 6.2)}${bar('Page de 40 segments', 6.0, 6.2)}${bar('4 requêtes simultanées', 6.0, 6.2)}${bar('Page de 40, deux cœurs occupés', 5.9, 6.1)}
  <div style="position:absolute;left:calc(420px + (100% - 420px) * .75);top:-8px;bottom:0;border-left:4px dashed ${JAUNE}"></div><div style="position:absolute;left:calc(420px + (100% - 420px) * .75 - 140px);top:-34px;font:700 19px 'Noto Sans'">budget du serveur : 6 s</div>
  <div style="position:absolute;right:0;top:-8px;bottom:0;border-left:4px solid ${AUB}"></div><div style="position:absolute;right:6px;top:-34px;font:700 19px 'Noto Sans'">limite du front : 8 s</div>
 </div>
</div>` };

// ------------------------------------------------------------------ 12. Ajouter une langue (six étapes)
const six = (n, t, cmd, opt) => `<div class="bev-s" style="background:${DOUX};padding:16px 16px 18px"><div style="display:flex;justify-content:space-between;align-items:center"><span class="pin" style="width:42px;height:42px;font-size:23px">${n}</span>${opt ? `<span class="chip" style="background:${BLEU};color:${AUB};font-size:16px;padding:1px 10px">facultatif</span>` : ''}</div><div class="t" style="font-size:25px;margin-top:10px">${t}</div><div class="mono" style="font-size:16.5px;margin-top:8px;line-height:1.35;">${cmd}</div></div>`;
figures.langue = { w: 1700, h: 430, scale: 1.5, html: `
<div style="width:1700px;padding:26px;background:#fff;display:grid;grid-template-columns:repeat(6,1fr);gap:14px">
 ${six(1, 'Créer le dossier', 'tools.new_language xx', false)}
 ${six(2, 'Mémoire par un natif', 'languages/xx/gold.csv', false)}
 ${six(3, 'Modèle', 'models/m2m_xx/', true)}
 ${six(4, 'Voix', 'organize_audio · import_audio', true)}
 ${six(5, 'Extension', 'src/languages.ts', false)}
 ${six(6, 'Vérifier', 'pytest · npm test', false)}
</div>` };

// ------------------------------------------------------------------ 13. Pétales de langues
const lang = (nom, actif, texte, c) => `<div style="text-align:center;width:230px">${flower(130, actif ? [ROSE, VERT, JAUNE, BLEU] : [GRIS, GRIS, GRIS, GRIS])}<div class="t" style="font-size:27px;margin-top:6px;${actif ? '' : 'color:#8c6f8f'}">${nom}</div><div style="font-size:18px;margin-top:2px;${actif ? '' : 'color:#8c6f8f'}">${texte}</div></div>`;
figures.langues = { w: 1700, h: 310, scale: 1.5, html: `
<div style="width:1700px;padding:26px 30px;background:#fff;display:flex;align-items:flex-start;gap:6px;justify-content:space-between">
 ${lang('Fulfulde', true, 'mémoire · voix · modèle', 0)}
 ${lang('Ghomálá’', false, 'à venir', 0)}${lang('Ewondo', false, 'à venir', 0)}${lang('Duala', false, 'à venir', 0)}${lang('Bassa', false, 'à venir', 0)}${lang('Bulu', false, 'à venir', 0)}${lang('Pidgin', false, 'à venir', 0)}
</div>` };

// ------------------------------------------------------------------ rendu
const only = process.argv[2];
const browser = await chromium.launch({ channel: 'chromium' });
for (const [name, fig] of Object.entries(figures)) {
  if (only && !name.startsWith(only)) continue;
  const ctx = await browser.newContext({ deviceScaleFactor: fig.scale });
  const p = await ctx.newPage();
  await p.setViewportSize({ width: fig.w, height: fig.h });
  await p.setContent(`<style>${css}</style><div id="f" style="width:${fig.w}px">${fig.html}</div>`);
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(250);
  await (await p.$('#f')).screenshot({ path: `${FIG}/${name}.png` });
  await ctx.close();
  console.log('figure', name);
}
await browser.close();
