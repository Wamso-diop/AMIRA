# Plan : back-end Amira

Spec : [../SPEC.md](../SPEC.md). Règles : [../CONSTRAINTS.md](../CONSTRAINTS.md). Tâches : [todo.md](todo.md).

## Vue d'ensemble

Une API Flask sans état. La chaîne d'un segment est : garde → mémoire validée → (hors catégories sensibles) NLLB local → contrôles → statut honnête. On construit de bas en haut, une étape à la fois, et chaque étape se termine par un commit, un résumé et un « go » humain (brief v2, §3).

## Graphe de dépendances

```
S0 environnement (modèle, mesures)
S1 contrat + squelette ──┬── S2 marqueurs ── S3 garde ──┬── S5 traduction par la mémoire ── S7 statuts
                         │                              │          │
                         └──────── S4 base + import gold┘          S6 moteur ─────────────────┘
                                                                   │
                         S8 voix / feedback / admin  (S1–S4)       S10 performance (S6)
                         S9 sécurité transversale (tout)           S11 livraison (tout)
```

## Décisions

- **Ordre du brief v2** (S0 → S11). Le moteur réel (S6) arrive après la mémoire (S5), qui reste la source principale.
- **Moteur injecté** : `create_app(engine=…)`. Les tests utilisent `FakeEngine` ou un espion ; seuls les tests `@pytest.mark.model` chargent NLLB.
- **Contrat par défaut** : `openapi.yaml` en YAML de style JSON, plus un petit validateur dans `tests/`, pour n'ajouter aucune dépendance (question ouverte 1 de la spec).
- **Les poids ne sont jamais commités** : `backend/models/` et `backend/data/*.sqlite3` sont ajoutés au `.gitignore` dès S0.

## Points de contrôle

| Après | Vérification |
|---|---|
| S0 | le modèle répond depuis le disque ; `docs/PERF.md` contient RAM et latence (1 et 8 segments) |
| S3 | marqueurs et garde couverts ; un canari refusé n'apparaît nulle part |
| S5 | `curl /v1/translate` sert une entrée du gold en `validated` sans moteur |
| S7 | parcours complet avec faux moteur, réponses validées contre `openapi.yaml` |
| S9 | tests de confidentialité et de fonctionnement hors ligne au vert |
| S11 | extension branchée, pastille « Prêt », `/ship` |

## Risques

| Risque | Impact | Parade |
|---|---|---|
| RAM disponible ≈ 1,9 Go pour un modèle de ≈ 2,5 Go en float32 | Haut (S0, S6, S10) | fermer des applications avant S0 ; mesurer ; sinon faire tourner les tests `model` sur une autre machine |
| Le modèle n'a appris que `{V1}`, `{V2}` | Haut (beaucoup de sorties `uncertain`) | `model_view`/`from_model`, puis mesurer le taux de marqueurs intacts en S6 |
| Lot de 40 au-delà de 6 s sur CPU | Moyen | la mémoire d'abord, puis un cache des sorties machine, puis CTranslate2 seulement si une mesure montre un gain (S10) |
| Les poids (2,4 Go) commités par erreur | Moyen | `.gitignore` en S0, avant le premier commit |
| `segmentKey` différent du front (UTF-16 ou code points) | Faible | test d'égalité sur 5 paires fournies par le front (S8) |
| Licence NLLB non commerciale | Haut pour une banque | `LICENSES.md` (S11) ; moteur remplaçable sans toucher au reste |
