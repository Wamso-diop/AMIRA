# Composants tiers utilisés

Liste destinée à la note technique du règlement SAFINUM Innovate Challenge.

## Inclus dans l'extension livrée (`dist/`)

| Composant | Version | Licence | Usage |
|---|---|---|---|
| React | 18.3.1 | MIT | Interface du panneau latéral |
| React DOM | 18.3.1 | MIT | Rendu du panneau |
| Inter Tight (via @fontsource/inter-tight) | 5.3.0 | SIL Open Font License 1.1 | Police des titres (graisses 800 et 900, sous-ensembles latin et latin-ext) |
| Noto Sans (via @fontsource/noto-sans) | 5.3.0 | SIL Open Font License 1.1 | Police du texte (400, 600 et 700, latin et latin-ext) |

Les polices sont embarquées dans l'extension : aucun CDN ni aucune ressource distante n'est chargé.
Elles affichent toutes deux les lettres du fulfulde ɓ Ɓ ɗ Ɗ ƴ Ƴ ŋ Ŋ ɲ Ɲ (vérifié avec fontTools).

Les icônes, les pétales, la flèche et les gribouillis sont des SVG dessinés pour Amira : pas de bibliothèque d'icônes.

## Outils de développement (non livrés)

| Outil | Version | Licence | Usage |
|---|---|---|---|
| Vite | 5.4.21 | MIT | Construction et serveur de développement |
| @vitejs/plugin-react | 4.7.0 | MIT | JSX et React dans Vite |
| TypeScript | 5.9.3 | Apache-2.0 | Typage |
| @types/chrome | 0.3.7 | MIT | Types des API d'extension Chrome |
| Vitest | 2.1.9 | MIT | Tests unitaires |
| jsdom | 25.0.1 | MIT | DOM simulé pour les tests unitaires |
| Playwright (@playwright/test) | 1.65.0 | Apache-2.0 | Tests de bout en bout, captures, lancement sur safinum.cm |
| sharp | 0.35.5 | Apache-2.0 | Génération des icônes 16/32/48/128 à partir du logo |
| Node.js | 22.23.4 LTS | MIT | Environnement d'exécution des outils |

## Services externes

Aucun. Le serveur de traduction Amira est développé par l'équipe et configuré par URL ; l'extension ne contacte rien d'autre.
