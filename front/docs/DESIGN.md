# Amira — plan de design du panneau

## Couleurs (mesurées sur le logo)

| Jeton            | Hex       | Rôle |
|------------------|-----------|------|
| `--aubergine`    | `#481C4B` | Texte, boutons pleins, contours (remplace le noir) |
| `--rose`         | `#E01D5B` | Accent, élément actif, alertes (formes, grands textes) |
| `--rose-texte`   | `#C2134C` | Rose pour petit texte et badge plein (contraste AA ≥ 4,5:1 sur blanc) |
| `--jaune`        | `#EFD109` | Zones d'accroche, rectangle incliné de mise en valeur (texte aubergine, 8,9:1) |
| `--vert`         | `#2DCF42` | « Validée », succès (fond ; texte aubergine dessus, 6:1) |
| `--bleu`         | `#2BB1EB` | Information, « Prêt » (fond ; texte aubergine dessus) |
| `--fond`         | `#FFFFFF` | Fond du panneau |
| `--fond-doux`    | `#F7F2F7` | Fond des champs et zones secondaires (aubergine à 4 %) |

Thème sombre : fond `#1F0E21`, texte `#F8EEF7`, l'aubergine devient la couleur des surfaces,
les accents restent identiques. Contraste élevé : contours 2 px, fonds secondaires blancs, rose texte encore plus sombre.

## Polices (locales, `@fontsource`, aucun CDN)

- **Inter Tight 800/900** : titres, navigation, boutons. Grotesque serrée et très grasse, cousine
  du mot « Amira » du logo. Interlignage 0,95, approche légèrement négative.
- **Noto Sans 400/600** : texte courant, champs, journal.
- Vérifié : les deux affichent ɓ Ɓ ɗ Ɗ ƴ Ƴ ŋ Ŋ ɲ Ɲ (sous-ensemble latin-ext).

Échelle (base 15 px, ratio ≈ 1,25) : 12 · 13,5 · 15 · 19 · 24 · 30 · 38 px. Taille de texte réglable
(90 → 130 %) par une variable `--zoom` appliquée à la racine.

## Grille

Panneau de 320 à 480 px. Gouttière 16 px, une seule colonne, contenu aligné à gauche.
Les blocs de réglage passent en 2 colonnes au-delà de 420 px seulement quand ce sont des paires courtes.

```
┌──────────────────────────────── en-tête fixe ┐
│ [logo Amira]                ( ● Prêt )        │
│ Lire. Comprendre. Agir.     [◯━ Traduire]     │
│ Traduire   Voix   Réglages   Journal          │  ← gras, actif souligné rose
├──────────────────────────────────────────────┤
│ ╱▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔╲ │  zone jaune en biseau
│ Cette page                                    │
│ en ▱fulfulde▱   ✿ pétales = langues           │  ← mot sur rectangle incliné
│ ╲▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁╱ │
│  12 traduits · 3 gardés en français · 0 err   │
│ De  [Détection auto ▾]   (⇄)                  │
│ Vers [Fulfulde (Adamaoua) ▾]                  │
│ Variété  (Ngaoundéré)(Garoua)(Maroua)         │
│ Affichage (Remplacer)(Bilingue)(Au survol)    │
│ [ Voir l'original ]  ← bouton rond plein      │
│ ── Traducteur rapide ──────────── ↙ flèche    │
│ ┌──────────────────────────────┐              │
│ │ saisie                        │             │
│ └──────────────────────────────┘              │
│ (Traduire)  (◎ copier)(◎ écouter)(◎ ⇄)        │
└──────────────────────────────────────────────┘
```

## Principes

1. **Un seul moment fort** : le titre géant sur la zone jaune en biseau, avec le mot clé posé sur
   un rectangle incliné et la flèche tracée à la main qui pointe vers la page. Tout le reste est calme.
2. **Les pétales sont fonctionnels** : le motif des 4 pétales sert d'indicateur de langue
   (pétale coloré = langue active, gris = bientôt), pas seulement de décor.
3. **Formes en biseau** plutôt qu'en arrondi généralisé : zones d'accroche et cartes d'état à coins
   coupés ; seuls les boutons et pastilles sont parfaitement ronds. Pas d'ombres grises, pas de dégradés.
4. **Trois gribouillis SVG au total** dans le panneau (en-tête de l'accueil, zone jaune, journal vide), en traits aubergine ou rose.
5. **Une seule animation** : l'entrée de la zone d'accroche à l'ouverture (désactivée par `prefers-reduced-motion` ou le réglage).
6. Casse normale partout, verbes d'action constants, pas de numérotation sauf pour l'accueil (vraie séquence de 3 écrans).

## Revue contre le brief

- Fond : blanc pur choisi plutôt que crème pour éviter le « crème + accent chaud » générique ; la chaleur vient du jaune de la marque.
- Pas de cartes identiques : l'état du serveur, les compteurs et le traducteur ont chacun une forme propre
  (bandeau, ligne de chiffres, champ encadré).
- Badges de fiabilité : formes différentes en plus de la couleur (cercle plein, losange, triangle ⚠) pour ne pas dépendre de la couleur seule.
