<div align="center">

<img src="preview.png" alt="Panneau Amira ouvert à côté d'une page : « Cette page en fulfulde », gros bouton Traduire" width="420" />

# Amira

### Lire. Comprendre. Agir.

**N'importe quel service financier en ligne, dans votre langue, sans toucher à une seule ligne de son code.**

Une extension Chrome qui s'ouvre à côté de la page de la banque, la rend lisible et audible en **fulfulde**,
et ne laisse jamais une traduction modifier un montant, un frais, un bénéficiaire ou un avertissement.

*Prototype pour le SAFINUM Innovate Challenge 2026*

</div>

---

## Tester en 3 minutes

**Il vous faut** : Chrome 116 ou plus récent, et Python 3.10 ou plus récent. Rien d'autre : pas de compte, pas de clé, pas de Node.js, pas d'Internet pour le serveur.

**1. Lancer le serveur** (un terminal, depuis le dossier du projet)

```bash
cd backend
python demo.py          # Windows : py demo.py
```

La première fois, le script crée son environnement et installe Flask tout seul (quelques secondes à une minute, avec Internet). Il affiche ensuite `Amira (ff) prête sur http://127.0.0.1:5000`. Laissez ce terminal ouvert.

**2. Installer l'extension** (Chrome)

`python demo.py` **ouvre tout seul un guide animé dans votre navigateur** (<http://127.0.0.1:5000/guide/>) : il montre, étape par étape, ce qui suit, avec le chemin exact du dossier `extension/` et un bouton pour le copier. Il commence par une démonstration : un clic sur **Traduire**, puis un clic pour **écouter** la voix d'un locuteur natif. Pas de navigateur graphique ? `python demo.py --no-browser`, puis ouvrir l'adresse à la main.

1. Ouvrir `chrome://extensions` et activer **Mode développeur** (en haut à droite).
2. Cliquer sur **Charger l'extension non empaquetée** et choisir le dossier **`extension/`** de ce dépôt.
3. Épingler Amira (icône puzzle, puis punaise).

**3. Essayer**

1. Ouvrir <https://safinum.cm/hackathon-test>, puis cliquer sur l'icône Amira : le panneau s'ouvre à côté de la page, la pastille indique **Prêt**.
2. Cliquer sur le gros bouton **Traduire** : la page passe en fulfulde, sur place. Les montants, numéros et dates n'ont pas bougé. **Voir l'original** revient à la page d'origine en un clic.
3. Onglet **Voix** : écouter la page, ou **La sélection**, puis toucher un passage sur la page pour l'entendre.
4. Onglet **Journal** : constater que seuls des codes techniques sont conservés, jamais le texte de la page.

> **Sans le modèle de traduction**, Amira sert la mémoire validée par les locuteurs natifs : tout ce qui est connu est traduit et marqué *validé*, et tout le reste **reste en original** au lieu d'être mal traduit. C'est voulu. Avec le modèle M2M100 affiné (dossier `backend/models/m2m_ff/`, non livré dans le dépôt à cause de sa taille : voir [backend/docs/MODEL.md](backend/docs/MODEL.md)), `demo.py` le détecte et le charge.
>
> **L'extension agit seule.** Sa mémoire validée et 130 voix de locuteurs natifs sont **dans le paquet** (`extension/`, 7,2 Mo compressé, aussi livré en `livrable/Amira-Extension.zip`) : sans serveur, la pastille indique « Prêt · autonome », la page est traduite par la mémoire validée et lue avec la voix des natifs ; un texte que la mémoire ne connaît pas reste en original. Le serveur lancé par `python demo.py` n'est qu'un renfort : s'il répond, il traduit en plus ce que la mémoire ne connaît pas. Si l'extension ne peut rien faire d'un texte, la page reste dans sa langue d'origine : elle ne casse jamais le site.

**Avec le modèle de traduction (facultatif, hors git)** : serveur local, depuis `backend/` :
1. Installer une fois : `.venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch==2.15.0 && .venv/bin/pip install -r requirements.txt -c constraints.txt` (`python demo.py` crée `.venv`).
2. Placer les 7 fichiers du modèle dans `backend/models/m2m_ff/` : `config.json`, `generation_config.json`, `model.safetensors`, `sentencepiece.bpe.model`, `vocab.json`, `tokenizer_config.json`, `added_tokens.json`.
3. Vérifier : `sha256sum models/m2m_ff/model.safetensors` doit donner la valeur de [backend/docs/MODEL.md](backend/docs/MODEL.md).
4. Lancer : `python demo.py`. Le message de démarrage indique « modèle M2M100 + mémoire validée » ; sans lui, « mémoire validée seule ».
Le dossier `models/` est ignoré par git : le modèle n'est jamais commité.

<details>
<summary><b>Autres façons de tester</b></summary>

| Je veux… | Commande |
|---|---|
| Voir le panneau à côté d'une fausse page bancaire, sans serveur ni Chrome | `cd front && npm install && npm run apercu` |
| Reconstruire l'extension moi-même (Node.js 20+) | `npm run extension` (à la racine) |
| Lancer les tests du serveur (435, plus 11 avec le vrai modèle) | installation complète décrite dans [backend/README.md](backend/README.md), puis `pytest` |
| Lancer les tests de l'extension (67, puis 8 de bout en bout dans un vrai navigateur) | `cd front && npm install && npm test && npm run test:e2e` |
| Tout le parcours (serveur réel, vraie extension, Chromium) | `bash backend/tools/e2e_extension.sh` |

</details>

---

## Ce qu'Amira apporte

### 1. Elle fonctionne sur le service tel qu'il est
Aucun script à intégrer, aucun accord de la banque, aucune modification du site. Amira est une **extension Chrome (Manifest V3)** : elle lit la page déjà affichée et la rend compréhensible. Elle a été conçue et testée sur des pages de structures très différentes : HTML simple, application d'une seule page, fenêtre modale, notification éphémère, iframe et shadow DOM, site qui change de langue. Les phrases coupées en balises (`<b>`, `<a>`…) sont traduites d'un seul tenant, **sans casser la mise en page**. Trois affichages au choix : remplacer, bilingue, ou original au survol.

### 2. Un montant ne passe jamais par la traduction

```
Sur la page            Votre solde est de 250 000 FCFA au 11/11/2026.
Masqué sur l'ordinateur Votre solde est de {N0} au {N1}.            ← seul ce texte quitte l'ordinateur
Traduit par le serveur  … {N0} … {N1} …
Vérifié sur l'ordinateur les marqueurs {N0} {N1} sont-ils tous là, une seule fois ?
                         ├─ oui → valeurs d'origine remises en place, traduction affichée
                         └─ non → le texte d'origine reste affiché, avec ⚠
```

- **Masquage local, non désactivable** : montants, devises, nombres, téléphones, e-mails, dates, références, IBAN et noms propres sont remplacés par des marqueurs **avant** tout envoi.
- **Double garde** : le serveur refuse lui aussi tout texte qui contiendrait une valeur sensible, et ne la cherche, ne la stocke et ne la journalise jamais.
- **Amira préfère ne pas traduire que mal traduire** : un marqueur perdu, ajouté ou dupliqué, un statut incertain, une erreur réseau : l'original reste affiché.
- **Avertissements de sécurité** et **frais** : affichés traduits seulement dans leur version validée par un locuteur natif.
- **Rien n'est touché** : Amira ne lit ni les cookies, ni les jetons de la page, ni ce que l'utilisateur saisit. Elle ne clique, ne remplit et ne soumet rien.
- **Aucune fuite, vérifiée** : journaux sans texte, serveur qui n'appelle rien vers l'extérieur (test avec connexions sortantes interdites), limites de débit, clés d'API, jeton et réseau interne pour les outils des natifs. Les tests de bout en bout exigent **100 % de marqueurs intacts et 0 fuite de valeur sensible**.

### 3. Elle s'adapte à ce qu'elle n'a jamais vu
- Un **observateur de page** repère tout texte qui apparaît après le chargement (message d'erreur, alerte, nouvelle étape d'un virement) et ne retraduit que ce passage.
- Pour un texte inconnu de la mémoire, le **modèle de traduction** prend le relais, sous seuil de confiance et avec les mêmes contrôles de sortie.
- Le **choix est mémorisé par site** : la traduction suit l'utilisateur de l'écran du solde jusqu'à la confirmation.
- La **langue de la page est détectée seule** (français ou anglais vers fulfulde, et fulfulde vers français ou anglais), sans réglage.
- Les avertissements qui s'affichent peuvent être **lus à voix haute automatiquement**.

### 4. Accessible avant d'être beau (et beau quand même)
- **On peut tout faire sans lire** : un gros bouton rond pour traduire, un autre pour écouter, des icônes qui gardent toujours le même sens.
- **Écouter** toute la page, les seuls messages importants, ou **les passages qu'on touche** sur la page, entourés en direct. Les **voix enregistrées par des locuteurs natifs** sont prioritaires sur la voix de synthèse, et clairement étiquetées.
- **Badges de fiabilité lisibles sans les couleurs** : cercle (validé), losange (automatique), triangle (à vérifier).
- **Réglages** : taille du texte, contraste élevé, thème sombre, animations réduites ; panneau en français ou en anglais.
- **Clavier** : **Alt + Maj + A** traduit ou rétablit la page, **Alt + clic** bascule un seul passage, **Échap** ferme l'outil de sélection. Panneau adapté de 320 à 480 px.

### 5. Une langue de plus, c'est un dossier de plus
Le fulfulde de l'Adamaoua est la première langue, pas la dernière (ghomálá', ewondo, duala, bassa, bulu, pidgin sont prévus). **Ajouter une langue ne change ni le moteur, ni la sécurité, ni l'API** :

```bash
cd backend && python -m tools.new_language bbj   # crée languages/bbj/ : fiche, mémoire vide, audio
```

Un locuteur natif remplit `languages/bbj/gold.csv`, on ajoute une ligne dans `front/src/languages.ts`, et c'est tout. Pas à pas : [backend/languages/README.md](backend/languages/README.md). Un test vérifie qu'une langue ajoutée est servie de bout en bout.

### 6. La qualité linguistique repose sur des personnes, pas sur du texte inventé
**Aucun mot de fulfulde n'est écrit, généré ni deviné par notre code.** Tout vient d'un fichier relu par un locuteur natif.
Chaque traduction porte un statut : `validated` (mémoire native), `machine` (modèle), `uncertain` (l'original reste). Depuis l'onglet Journal, l'utilisateur peut signaler une traduction et proposer une correction, elle aussi masquée avant envoi ; un natif la valide et elle devient `validated` pour tous. Un locuteur enregistre un passage une fois, et sa voix est lue partout où ce passage apparaît.

### 7. Construit pour être repris
- **Contrat d'API figé et documenté** : [front/docs/API.md](front/docs/API.md) et [backend/docs/openapi.yaml](backend/docs/openapi.yaml). L'extension ne connaît que l'adresse du serveur, fixée à la construction.
- **Serveur indépendant** : Flask, SQLite, aucune dépendance cloud ; le moteur de traduction se remplace sans toucher au reste.
- **531 tests automatisés** (450 serveur dont 11 avec le vrai modèle, 81 extension) plus 8 tests de bout en bout dans un vrai navigateur.
- **Documentation** : [conception](backend/SPEC.md), [règles de qualité](backend/CONSTRAINTS.md), [masquage](backend/docs/MASQUAGE.md), [exploitation](backend/docs/EXPLOITATION.md), [mesures de performance](backend/docs/PERF.md), [design](front/docs/DESIGN.md), [licences](backend/LICENSES.md), [composants tiers](front/docs/COMPOSANTS-TIERS.md). **Aucun service externe**, polices et icônes embarquées.

---

## Architecture

```
┌──────────── Chrome ────────────────────────────────────────┐
│  Page de la banque (inchangée)        Panneau latéral Amira │
│  ┌─────────────────────────┐          ┌──────────────────┐  │
│  │ Script de contenu       │◄────────►│ React            │  │
│  │ · découpage en passages │ messages │ Traduire · Voix  │  │
│  │ · masquage local        │          │ Réglages ·Journal│  │
│  │ · vérification          │          └──────────────────┘  │
│  │ · observation en direct │                                │
│  └───────────┬─────────────┘                                │
│              │ textes MASQUÉS uniquement                    │
│  ┌───────────▼─────────────┐                                │
│  │ Service worker          │ cache · nouvelles tentatives · │
│  │                         │ journal sans données           │
│  └───────────┬─────────────┘                                │
└──────────────┼─────────────────────────────────────────────┘
               │ /v1/translate · /v1/tts · /v1/feedback
       ┌───────▼────────────────────────────┐
       │ API Amira (Flask)                  │
       │ garde → mémoire validée → modèle   │  une langue = backend/languages/<code>/
       └────────────────────────────────────┘
```

## Dépôt

```
AMIRA/
├── extension/             l'extension construite : à charger telle quelle dans Chrome
├── front/                 code source de l'extension (TypeScript, React, Vite)
│   ├── src/languages.ts   la langue cible (le seul fichier à toucher pour en ajouter une)
│   ├── src/content/       découpage, masquage, vérification, observation de la page
│   ├── src/panel/         panneau latéral
│   └── docs/              API.md · DESIGN.md · COMPOSANTS-TIERS.md · captures/
├── livrable/              les livrables de l'épreuve : description, script vidéo, note technique, documentation complète (PDF et Markdown)
└── backend/               API Flask
    ├── demo.py            lancement en une commande
    ├── languages/<code>/  une langue : fiche, mémoire validée, voix, phrases de contrôle
    ├── amira/             garde, masquage, moteur, routes
    ├── tools/             import de la mémoire et des voix, création d'une langue
    └── docs/              openapi.yaml · MASQUAGE.md · EXPLOITATION.md · PERF.md
```

## Limites connues

Nous préférons les écrire nous-mêmes :

- **Testé sur Chrome et Chromium uniquement.** Les pages internes de Chrome ne sont pas accessibles aux extensions.
- **La qualité du fulfulde dépend des locuteurs natifs.** La mémoire validée couvre l'environnement de test du concours ; le reste est traduit par le modèle, marqué comme tel, et gardé en original en cas de doute.
- **Les navigateurs n'ont pas de voix fulfulde.** Sans enregistrement natif pour un passage, la voix de synthèse est clairement étiquetée comme telle.
- **Le panneau n'est pas encore traduit en fulfulde** (il est en français et en anglais) : nous refusons de générer cette traduction sans locuteur natif.
- **Licences** : M2M100 est sous licence MIT. Le droit d'usage de la mémoire validée reste à confirmer par le locuteur natif ([LICENSES.md](backend/LICENSES.md)).
- Le texte dessiné dans des images ou des `<canvas>` n'est pas traduit.
- Le serveur de démonstration (`demo.py`) est fait pour une machine locale ; la production passe par gunicorn derrière la passerelle de la banque ([EXPLOITATION.md](backend/docs/EXPLOITATION.md)).

---

<div align="center">

**Amira** : parce que comprendre sa propre banque ne devrait pas demander de traducteur.

</div>
