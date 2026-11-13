# Contraintes du back-end Amira

Dernière relecture : 2026-11-12. Source : le brief initial (version 2, non conservé dans le dépôt), sections 2, 5 et 6.
Ce fichier ne s'affaiblit jamais pour faire passer un changement. Le resserrer est libre ; l'assouplir
se discute en revue, dans un commit séparé.

## Les dix règles (brief v2, section 6)

1. Aucune donnée réelle ne sort du navigateur ; le serveur la refuse si elle arrive.
2. « validated » = relu par un natif, et rien d'autre.
3. Avertissements de sécurité et frais : mémoire uniquement.
4. Marqueurs intacts, même nombre, ou on déclare le doute.
5. Aucun texte dans les journaux, les exceptions ou les métriques.
6. Aucun appel sortant dans translate, tts, feedback.
7. Tout nouveau comportement est précédé d'un test qui échoue.
8. Réponses conformes à docs/openapi.yaml.
9. Une étape à la fois, validée par un humain.
10. Le moins de code possible, sauf pour le code de sécurité.

Le détail et le test qui vérifie chaque règle suivent.

Le contrat (`front/docs/API.md`, `front/src/services/api.ts`) fait foi : aucun champ renommé, retiré
ou changé. `/v1` ne fait qu'ajouter.

## Plancher (toujours, sans outil)

- Aucun nouveau `# noqa`, `# type: ignore`, `pytest.mark.skip` ou `xfail` sans raison dans le message de commit.
- Aucun bouchon : `raise NotImplementedError`, `except: pass`, `except Exception: pass`.
- Aucun secret dans les sources (jeton admin, clés d'API) : seulement dans `.env`, jamais commité.
- Aucun test supprimé ni affaibli (assertion retirée) pour passer au vert.
- Chaque raccourci porte un commentaire `shortcut: <limite>, <quand le lever>`.

## Principes non négociables (P1–P6)

| # | Règle | Vérifié par |
|---|---|---|
| P1 | Aucune donnée réelle (montant, nom, numéro, e-mail, IBAN) n'atteint le moteur, la base, les journaux ni le réseau. | `tests/test_guard.py`, `tests/test_privacy.py` (canari, moteur espion) |
| P2 | `validated` uniquement pour une entrée de la mémoire relue par un natif, jamais pour une sortie du moteur. | `tests/test_status.py` |
| P3 | `categoryHint` = `security_warning` ou `fees` : mémoire validée UNIQUEMENT, le moteur n'est jamais appelé. | `tests/test_status.py` (moteur espion), `tests/test_cache.py` (jamais servi par le cache) |
| P4 | Chaque marqueur revient intact, le même nombre de fois, `{B}` bien imbriqués. Le moteur n'ajoute aucun chiffre. | `tests/test_markers.py`, `tests/test_engine.py` |
| P5 | Dans le doute : `uncertain` + texte source masqué. | `tests/test_engine.py`, `tests/test_truncation.py` |
| P6 | Fonctionne sans Internet. Aucun appel sortant pendant translate, tts, feedback. | `tests/test_offline.py` (socket bloqué), réseau interne de la passerelle |
| P7 | Aucun fulfulde écrit à la main dans le code ou les tests : les exemples viennent du CSV gold ou de fixtures de données. | `tests/test_no_fulfulde.py` |

## Sécurité (section 5)

| Règle | Seuil | Vérifié par |
|---|---|---|
| Journaux | méthode, chemin, statut, durée, requestId, compteurs. Jamais de texte, même masqué, ni de corps. | canari dans `tests/test_privacy.py` (caplog) |
| Exceptions | aucun message ne contient de texte utilisateur | `tests/test_privacy.py` (moteur qui lève) |
| Debug | désactivé hors développement | `tests/test_app.py` |
| Feedback | écrit seulement dans `pending`, après la garde ; jamais `validated` | `tests/test_feedback.py` |
| Admin | jeton comparé en temps constant (`hmac.compare_digest`), 401 sans jeton, nom du natif obligatoire, audit (qui, quand, quoi) ; réseaux validés au démarrage ; adresse réelle derrière un proxy de confiance | `tests/test_admin.py`, `tests/test_proxy.py` |
| Limites | 40 segments, 1000 caractères/segment, 256 Ko/JSON, 5 Mo/audio | `tests/test_translate_memory.py`, `tests/test_limits.py`, `tests/test_admin.py` |
| Débit | 429 + `retryAfterMs` | `tests/test_limits.py`, `tests/test_proxy.py` |
| Délai moteur | 6 s max par lot (le front coupe à 8 s) | `tests/test_engine.py` (moteur lent factice), `tests/test_perf.py` (vrai modèle) |
| Rétention | `pending` et `unmatched` purgés après `AMIRA_RETENTION_DAYS` (90 par défaut) | `tests/test_limits.py` |
| CORS | limité à `AMIRA_ALLOWED_ORIGINS` en production ; `X-Amira-Voice` exposé | `tests/test_app.py` |
| Dépendances | versions figées (`==`) ; aucune vulnérabilité connue | `pip-audit -r requirements.txt` (avis externe) |

Dépendances autorisées : Flask, gunicorn, python-dotenv, pytest ; transformers/torch (ou ctranslate2)
**uniquement dans `amira/engine.py`**. Tout le reste : bibliothèque standard. Pas d'ORM, pas de file de
tâches, pas de micro-services.

## À ne pas faire (section 8)

| Interdit | Vérifié par |
|---|---|
| Écrire du fulfulde dans le code ou les tests | `tests/test_no_fulfulde.py` : aucune valeur de la colonne `ff` de `gold_fulfulde.csv` n'apparaît dans `amira/` ni `tests/` (ignoré si le CSV est absent) |
| Produire `validated` sans relecture d'un natif | P2 |
| Journaliser ou stocker un texte non masqué ; journaliser un texte quelconque | P1, journaux |
| Changer le contrat du front | `tests/openapi_check.py`, appelé par `test_app.py`, `test_translate_memory.py`, `test_status.py`, `test_voice.py`, `test_feedback.py`, `test_limits.py` |
| Ajouter une dépendance non indispensable | revue de `requirements.txt` |

## Commandes

| Étape | Commande | Budget |
|---|---|---|
| après chaque modification | `cd backend && pytest -q` (les tests `model` sont ignorés par défaut) | < 10 s |
| fin de tâche, CI | `pytest -q && pip-audit -r requirements.txt` | minutes |
| avant livraison | `pytest -q -m model` (vrai modèle, lot de 40 : médiane et p95 dans `docs/PERF.md`) + bout en bout avec l'extension | manuel |

## Mesuré, pas encore imposé

| Mesure | Aujourd'hui | Sens |
|---|---|---|
| Lot de 40 segments, vrai modèle CPU | à mesurer | p95 < 6 s visé ; ne doit pas se dégrader |
| Seuil de confiance du moteur | 0,5 (non calibré) | à calibrer sur le fichier relu par le natif |

## Exceptions

| ID | Règle | Chemin | Raison | Responsable | Expire |
|---|---|---|---|---|---|
| — | | | | | |
