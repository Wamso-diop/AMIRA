# Amira

Extension Chrome (Manifest V3) qui rend un service financier numérique compréhensible dans une langue
nationale camerounaise, **sans modifier le code du site**. Première langue : le fulfulde (Adamaoua),
depuis le français et l'anglais, et inversement.

Prototype de l'équipe Amira pour le SAFINUM Innovate Challenge.
Environnement de test officiel : <https://safinum.cm/hackathon-test>.

> Ce dépôt contient le **front** : panneau latéral, script de contenu, masquage local, couche de services,
> journal et tests. La traduction, la voix et la fiabilité sont assurées par un serveur séparé, branché
> par son URL (voir [docs/API.md](docs/API.md)). Aucun texte en fulfulde n'est inventé ici.

## Prérequis

- Node.js 20 ou plus récent (testé avec 22 LTS) et npm
- Google Chrome ou Chromium 116+ (API `chrome.sidePanel`)

## Installer l'extension dans Chrome

```bash
export PATH="$HOME/.local/node/bin:$PATH"   # si npm n'est pas trouvé
npm install
npm run build        # → dist/
```

1. Ouvrir `chrome://extensions`, activer le **mode développeur** (en haut à droite).
2. **Charger l'extension non empaquetée** → choisir le dossier `dist/`. Amira apparaît avec son logo.
3. **Épingler** : icône puzzle 🧩 de la barre d'outils → épingle à côté d'Amira.
4. Sur **n'importe quel site**, cliquer sur l'icône Amira : le panneau s'ouvre à droite et la page se resserre à côté
   (rien n'est caché ; la largeur se règle en tirant le bord du panneau).
5. Activer **Traduire cette page**. La première fois sur un site autre que safinum.cm, Chrome demande une seule fois
   l'autorisation d'accéder aux sites web ; Amira ne lit une page que lorsque cet interrupteur est activé.

Après une modification du code : `npm run build`, puis le bouton ↻ d'Amira dans `chrome://extensions`.
Les pages internes de Chrome (`chrome://…`, boutique Chrome) ne peuvent pas être traduites : Chrome l'interdit à toutes les extensions.

## Mode autonome (l'extension agit seule)

`npm run jury` construit `../extension/` en **mode autonome** (`VITE_AMIRA_MODE=embedded`) : la mémoire validée (`src/data/memory.json`) et les voix (`public/audio/`) sont dans le paquet, et le serveur local est un simple renfort (« hybride »). Ces données viennent de `backend/languages/<code>/` : `npm run data` les régénère (budget des voix : 8 Mo, pour tenir dans 10 Mo). Les règles de la mémoire sont celles du serveur, portées à l'identique ; `tests/unit/embedded.test.ts` les compare aux réponses du vrai serveur sur plus de 2 000 requêtes. Test sans serveur dans un vrai navigateur : `node scripts/e2e-autonome.mjs`.

## Développer : `npm run dev`

```bash
npm run dev
```
- construit `dist/` puis le **reconstruit à chaque modification** du code ;
- ouvre le **guide animé** (9 étapes, `guide.html`) : démonstration (traduire, écouter), puis `chrome://extensions`, mode développeur,
  chargement du dossier, épingle, utilisation. Les jurés le reçoivent par `python demo.py` : il est **construit dans `backend/guide/`** (`npm run guide`) et servi par le serveur à `/guide/`. Après une modification du guide : `npm run guide`, puis commiter `backend/guide/`.

Après une modification : bouton ↻ d'Amira dans `chrome://extensions`, puis recharger la page.
`npm run apercu` affiche le panneau à côté d'une page bancaire fictive, sans installer l'extension.

## Brancher le back-end (développeur du back-end)

Il n'y a rien à régler dans l'extension : l'adresse du back-end est fixée à la construction.
**Pour une démonstration locale**, `npm run jury` (ou `npm run extension` à la racine) construit l'extension branchée sur `http://localhost:5000` dans `../extension/`, prête à charger ; le serveur se lance avec `python demo.py` dans `backend/`.

```bash
cp .env.example .env
# dans .env :  VITE_AMIRA_API_URL=https://api.exemple.cm
npm run build
```
La construction ajoute cette origine aux autorisations du manifeste. Tant que `VITE_AMIRA_API_URL` est vide,
l'extension utilise la simulation : le texte revient préfixé de `⟦FF⟧` (aucun faux fulfulde), la pastille affiche « démo ».
Le contrat (requêtes, réponses, erreurs) est dans [docs/API.md](docs/API.md). Aucun secret ni clé d'API dans l'extension.

## Utilisation

- **Traduire cette page** (en-tête) ou **Alt + Maj + A** : traduit ou rétablit la page. Le choix est mémorisé par site.
- La langue de la page est **détectée automatiquement** : français ou anglais → fulfulde ; fulfulde → français ou anglais (au choix). Jamais français ↔ anglais.
- **Voir l'original** : retour instantané à la page d'origine, sans nouvel appel au serveur. **Alt + clic** sur un passage : bascule ce passage seul.
- Affichage : Remplacer, Bilingue (traduction sous l'original), Original au survol.
- ⚠ devant un passage : la traduction n'était pas assez sûre, l'original est gardé.
- Sites : `safinum.cm` est autorisé dès l'installation ; pour tout autre site, Chrome demande l'accord une seule fois (révocable dans **Réglages → Sites web**).

## Sécurité et confidentialité

- Masquage **local** avant tout envoi : montants, devises, nombres, téléphones, e-mails, dates, références, noms propres
  (heuristique, plus les noms repérés ailleurs sur la page). Non désactivable.
- Le script de contenu ne lit jamais les balises meta (jeton CSRF), les cookies ni les valeurs des champs. Il ne clique, ne remplit et ne soumet rien.
- Le serveur doit renvoyer exactement les mêmes marqueurs ; sinon, si le statut est incertain, ou en cas d'erreur, le texte d'origine reste affiché.
- Les avertissements de sécurité ne s'affichent traduits que dans leur version validée.
- Le journal ne contient que l'hôte et des codes techniques, jamais le texte de la page.

## Tests

```bash
npm test             # Vitest : masquage, vérification des marqueurs, segmentation par blocs (59 tests)
npx playwright install chromium   # une fois
npm run test:e2e     # Playwright : 5 pages locales + scénarios d'erreur (7 tests)
npm run safinum      # construit dist/ et lance l'extension sur https://safinum.cm/hackathon-test (mode démonstration)
npm run screens      # captures du panneau à 320, 400 et 480 px → docs/captures/
```

Pages de test ([tests/e2e/pages/](tests/e2e/pages/)) : HTML simple, application monopage, fenêtre modale, notification éphémère,
iframe (+ shadow DOM). Chacune reproduit une partie du parcours : solde, frais, bénéficiaire, récapitulatif, erreur, avertissement de sécurité.
Mesures écrites dans `tests/e2e/results/metrics.json` : texte couvert, part traduite, marqueurs intacts (100 % exigé), fuites de valeurs sensibles (0 exigé), temps de traitement.

## Organisation

```
public/manifest.json        manifeste MV3 (accès par défaut : https://safinum.cm/* uniquement)
src/background/             service worker : routeur, cache, journal, sites ajoutés à la demande
src/content/                script de contenu : segmentation, masquage, vérification, moteur, styles injectés
src/services/               api.ts (contrat + client HTTP), mock.ts, settings.ts, log.ts
src/panel/                  panneau React : en-tête, 4 onglets, accueil
src/languages.ts            la langue cible (seul fichier à modifier pour en ajouter une : backend/languages/README.md)
src/locales/                fr.json, en.json ; ff.json vide (à rédiger par un locuteur natif) ; {lang} = nom de la langue cible
scripts/                    icônes, captures, lancement sur safinum.cm
docs/                       API.md, DESIGN.md, COMPOSANTS-TIERS.md, captures/
```

Logos sources : `amira.png` (symbole) et `amora_nom.png` (logo complet), à la racine. `npm run icons` régénère les icônes.

## Composants tiers

Voir [docs/COMPOSANTS-TIERS.md](docs/COMPOSANTS-TIERS.md).
