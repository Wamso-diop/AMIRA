# Mesures de performance

> NLLB a été évalué puis retiré le 2026-11-14 : les sections « S0 », « S6 », « S10 et S11 » et « Correctif du 2026-11-12 » ci-dessous sont des **mesures historiques faites avec NLLB**, conservées comme trace. Le moteur livré est M2M100 (première section).

## M2M100 : le vrai modèle, par le service (2026-11-14)

Même machine que S0 (i7-6820HQ, CPU seulement, 15,8 Go de RAM). `AMIRA_MODEL_FAMILY=m2m100`, modèle `models/m2m_ff`
(voir `docs/MODEL.md`), torch 2.15.0+cpu à 4 fils, `num_beams=4`, `max_new_tokens=96`, budget du service 6 s, paquets de 4.
Mesure : requêtes `POST /v1/translate` complètes (masquage, mémoire, moteur), **cache vide à chaque essai**, textes français
inconnus du gold. Les `p95` portent sur 10 essais (20 pour les requêtes simultanées) : à ce volume, ils sont proches du maximum.

| Scénario | Essais | Médiane | p95 | Max | Statuts |
|---|---|---|---|---|---|
| 1 segment | 10 | 1,86 s | 1,89 s | 1,89 s | 1 `machine` |
| 8 segments | 10 | 5,63 s | **6,21 s** | 6,21 s | 8 `machine` |
| Lot de 40 (20 gold + 20 inconnus) | 10 | 5,92 s | **6,25 s** | 6,25 s | 20 `validated`, 8 `machine`, 12 `uncertain` |
| 4 requêtes simultanées (lots différents) | 20 | 6,00 s | **6,24 s** | 6,24 s | 4 `machine` pour une requête sur deux, 0 pour les autres |

**Le p95 dépasse 6 s** pour 8 segments, le lot de 40 et les requêtes simultanées. Le dépassement est de 0,2 à 0,25 s au-dessus
du budget de 6 s du service (plafond de génération + traitement autour), et reste **sous les 8 s** après lesquelles le front coupe.

| RAM | Valeur |
|---|---|
| RSS après chargement et échauffement | 2 266 Mo |
| RSS finale après les mesures | 2 474 Mo |
| RSS maximale du processus | 2 745 Mo |

Moteur seul (`python -m tools.check_model`, 3 essais) : chargement 2,5 s ; 1 segment médiane 1,92 s (max 2,03 s) ;
8 segments en un lot médiane 4,74 s (max 4,99 s) ; RSS max 447 Mo en `check_model` au chargement puis 2 884 Mo en fin de mesure.

Pour comparaison, les mesures NLLB de la même machine (ci-dessous, S0 et S10) : 1 segment 1,94 s, 8 segments 6,19 s, lot de 40 médiane 3,55 s
avec 4 segments inconnus traduits. Avec M2M100, le lot de 40 en traduit 8 mais prend 5,92 s : le moteur utilise tout le budget.


**Nombre d'essais** : les p95 de ce tableau portent sur **10 essais** (20 pour les requêtes simultanées). À ce volume, ils sont proches du maximum.

**Décision (2026-11-14)** : un p95 de 6,2 s est acceptable, la limite réelle du front étant de 8 s. Le budget (6 s) et `num_beams` (4) ne changent pas.

### Sous charge : deux cœurs occupés (2026-11-14)

Mêmes scénarios, pendant que deux processus Python tournaient en boucle (charge système 2,4), pour simuler le navigateur et l'enregistrement d'écran. Même nombre d'essais.

| Scénario | Médiane | p95 | Max | Statuts (dernier essai) |
|---|---|---|---|---|
| 1 segment | 2,02 s | 2,06 s | 2,06 s | 1 `machine` |
| 8 segments | 5,75 s | 6,26 s | 6,26 s | 6 `machine`, 2 `uncertain` |
| Lot de 40 | 5,87 s | **6,12 s** | 6,12 s | 20 `validated`, 8 `machine`, 12 `uncertain` |
| 4 requêtes simultanées | 6,00 s | 6,41 s | 6,41 s | 4 `machine` pour une requête sur deux (8 dans un tour) |

RSS maximale du processus : 2 735 Mo. Seuil d'arrêt fixé à 7,5 s pour le lot de 40 : non atteint (6,12 s).
La charge coûte surtout aux segments : avec 2 cœurs pris, 8 segments inconnus n'en voient plus que 6 traduits (le plafond de 6 s coupe la génération).

### Comparaison avec la référence humaine : pourquoi 13 sur 56 et non 17 sur 56

`tests/fixtures/m2m_colab_reference.csv`, 56 phrases (fr et en vers ff). La sortie du serveur est **identique** à la colonne `m2m100` de Colab (56 sur 56) ; seule la façon de comparer à la colonne `reference` change le score :

| Normalisation | Serveur | Colab M2M100 | Colab NLLB |
|---|---|---|---|
| Aucune (égalité exacte) | 13 sur 56 (23,2 %) | 13 sur 56 (23,2 %) | 12 sur 56 |
| Casse ignorée | 16 sur 56 (28,6 %) | 16 sur 56 | 13 sur 56 |
| Casse et ponctuation finale ignorées | **17 sur 56 (30,4 %)** | **17 sur 56 (30,4 %)** | 13 sur 56 |
| Casse et toute la ponctuation ignorées | 17 sur 56 | 17 sur 56 | 13 sur 56 |

Les 17 sur 56 (30,4 %) du notebook correspondent à la comparaison sans casse ni ponctuation finale. Le 13 sur 56 est la comparaison exacte. Le modèle et ses sorties sont les mêmes des deux côtés : aucun écart de ce côté.

---

## S0 : modèle seul (2026-11-12)

Machine : Intel Core i7-6820HQ (4 cœurs, 8 fils), 15,8 Go de RAM, CPU seulement.
torch 2.15.0+cpu (4 fils), transformers 5.22.2, modèle `models/nllb_ff` en float32, `num_beams=4`, `max_new_tokens=96`.
Commande : `.venv/bin/python tools/check_model.py`

| Mesure | Valeur |
|---|---|
| Chargement depuis le disque | 4,7 s |
| RSS maximale du processus | 3 810 Mo |
| 1 segment (médiane de 3 essais) | 1,94 s |
| 8 segments en un lot (médiane de 3 essais) | 6,19 s (max 6,26 s) |
| Phrase de contrôle de Colab | sortie identique, confiance 0,83 |
| Confiance sur 5 phrases hors gold | 0,64 à 0,73 |

### Lecture

- **Le budget de 6 s est déjà atteint avec 8 segments.** Par extrapolation, un lot de 40 segments traduits par le moteur prendrait environ 30 s : impossible dans le délai de 8 s du front.
- **Conséquence pour S6 et S10** : le moteur ne traitera, dans chaque requête, que ce qui tient dans le budget de 6 s. Le reste reviendra `uncertain` (le front garde l'original). La mémoire et un cache des sorties machine porteront l'essentiel. CTranslate2 int8 (gain annoncé de 3 à 4 fois sur CPU) ne sera essayé que si une mesure le justifie, comme le prévoit le brief.
- **RAM** : prévoir au moins 4 Go pour le conteneur.
- **Confiance** : les phrases hors gold donnent de 0,64 à 0,73. Avec un seuil de 0,5, tout passerait en `machine` : le seuil reste à calibrer sur un fichier relu par le natif.

## S6 : marqueurs à travers le vrai modèle (2026-11-12)

10 phrases masquées (fr → ff), passées par la chaîne complète (`model_view` → NLLB → `from_model` → contrôles), budget ouvert à 60 s :

| Mesure | Valeur |
|---|---|
| Marqueurs intacts (`{N}`, `{B}…{/B}`, `{E}`) | 10 sur 10 |
| Statut | 10 `machine` |
| Confiance | 0,51 à 0,90 |
| Durée du lot de 10 | 15,8 s |

Lecture : la conversion en `{V1}`, `{V2}`… fonctionne. Avec un seuil de 0,5, presque tout passe : il faut **calibrer** sur le fichier relu par le natif. Avec le budget réel (6 s), environ 4 segments par requête passent par le moteur ; les autres reviennent `uncertain`.

## S10 et S11 : lot de 40, mémoire, moteur et cache (2026-11-12)

Commande : `pytest -m model -s tests/test_perf.py`. Même machine (CPU seulement) ; budget de 6 s, paquets de 4, 0,8 s estimées par segment. Le lot : la même page de 40 segments, soit **20 textes du gold** (servis par la mémoire) et **20 textes inconnus** (moteur ou rien).

### Une requête, sans cache (S10)

| Mesure | Valeur |
|---|---|
| Durée (5 essais) | médiane 3,55 s, p95 3,77 s |
| Textes du gold | 20 sur 20 `validated` |
| **Textes inconnus traduits** | **4 sur 20** (`machine`) |
| **Textes inconnus non traduits** | **16 sur 20** (`uncertain` : le front garde l'original) |

**Le 3,55 s ne mesure pas une page traduite.** Il couvre 20 segments servis par la mémoire, presque gratuits, et seulement 4 des 20 segments inconnus. Un paquet de 4 prend environ 3,5 s, le suivant ne tient plus dans le budget. Sans cache, chaque visite redemandait les mêmes 16 segments et retraduisait les mêmes 4 : une page avec plus de 4 textes inconnus n'en avait jamais plus de 4 traduits.

### Visites successives de la même page, avec le cache des sorties machine (S11)

| Visite | Durée | Gold `validated` | Inconnus traduits (`machine`) | dont servis par le cache | Inconnus non traduits (`uncertain`) |
|---|---|---|---|---|---|
| 1 | 3,13 s | 20 | 4 | 0 | 16 |
| 2 | 3,44 s | 20 | 8 | 4 | 12 |
| 3 | 3,53 s | 20 | 12 | 8 | 8 |
| 4 | 3,68 s | 20 | 16 | 12 | 4 |
| 5 | 4,24 s | 20 | 20 | 16 | 0 |
| 6 et 7 | < 0,01 s | 20 | 20 | 20 | 0 |

Lecture :
- Chaque visite ajoute 4 traductions (un paquet par requête) ; la page entière est couverte à la 5ᵉ visite. Le cache est partagé : ce sont les visites **de tous les utilisateurs** qui comptent, pas celles d'une seule personne.
- Le choix des segments envoyés au moteur est fixe : erreurs et instructions d'abord, puis les textes courts. Un texte refusé n'est pas retenté pendant 10 minutes (cache négatif), pour ne pas occuper les 4 places.
- Le cache est en mémoire vive (texte masqué seulement), vidé à chaque redémarrage ; ses sorties restent `machine`, jamais `validated`. La seule couverture durable reste la mémoire validée par le natif.

### Requêtes simultanées

4 requêtes en même temps, sur des lots différents : 2,81 s à 3,09 s chacune, toutes sous les 8 s. **Une seule requête profite du moteur** (4 segments traduits, 0 pour les trois autres) : le modèle ne fait qu'une génération à la fois, et les requêtes qui attendent rendent la main avant les 8 s, avec des segments `uncertain`.

### Échauffement

Une phrase est traduite pendant le chargement, avant que `/v1/ready` passe au vert. Gain faible (premier appel 1,6 s, suivant 1,4 s) : l'écart vient surtout des phrases elles-mêmes.

### Ce qui n'a pas été fait

- CTranslate2 : le brief interdit de convertir le modèle (§5), et la latence tient dans le budget.
- La qualité des sorties `machine` n'est pas mesurée ici (chrF++ 44,7 sur 29 entrées, selon le brief) ; le seuil de confiance de 0,5 laisse passer presque tout et reste à calibrer avec le natif.

## Lire le compteur `unmasked_total` sur la page de test réelle

`unmasked_total` compte les segments refusés par la garde : une trace de donnée réelle (chiffre, devise, e-mail) que le masquage n'a pas retirée. Ce compteur ne contient aucun texte. Pour le lire après une visite de https://safinum.cm/hackathon-test avec l'extension branchée sur le serveur :

```bash
cd backend
# avant la visite
.venv/bin/python -c "import sqlite3; print(dict(sqlite3.connect('data/amira.sqlite3').execute('SELECT name, value FROM counters')))"
# visiter la page avec l'extension (pastille « Prêt »), activer la traduction, puis relire le compteur
.venv/bin/python -c "import sqlite3; print(dict(sqlite3.connect('data/amira.sqlite3').execute('SELECT name, value FROM counters')))"
```

- La différence entre les deux lectures = le nombre de segments de la page refusés par la garde. Le journal du serveur donne le même nombre, requête par requête : `refused=<n>` sur chaque ligne `POST /v1/translate`.
- Si `AMIRA_DB_PATH` est réglé, lire ce fichier au lieu de `data/amira.sqlite3`.
- Un compteur qui augmente signale un trou dans le masquage du front. C'est le cas, par exemple, de « francs CFA » écrit sans montant, que le front ne masque pas et que la garde refuse volontairement (voir `docs/MASQUAGE.md`). Ce compteur ne donne pas la liste des textes concernés : le serveur ne les garde jamais.

## Correctif du 2026-11-12 : textes longs et délai du front

**Constat sur la vraie page** : `POST /v1/translate` en 8,4 s, puis 9,3 s (28 segments). Le front coupe à 8 s et ne montre rien, même les segments servis par la mémoire. Sur le serveur, **un paquet de 4 phrases longues prenait 16,9 s**. Les mesures de S10 ne portaient que sur des phrases **courtes** : l'estimation fixe de 0,8 s par segment était 5 fois trop basse pour des textes réels.

**Correctif** :
- **Plafond dur** : `generate()` reçoit `max_time`, le temps restant avant l'échéance. Les phrases inachevées n'ont pas de `</s>`, donc leur confiance vaut 0 et elles reviennent `uncertain`.
- **Estimation remesurée par le moteur après chaque génération** : elle remonte aussitôt si le moteur est plus lent que prévu, et ne redescend que de moitié s'il est plus rapide. La tentative stricte compte double.
- **Taille du paquet** : calculée sur le temps restant, au lieu d'être fixée à 4.

| 28 phrases longues, vrai modèle (`pytest -m model -s tests/test_deadline.py`) | Durée | Traduites par le moteur |
|---|---|---|
| 1re requête (estimation de départ 0,8 s, trop basse) | 6,32 s | 0 (paquet coupé à l'échéance) |
| 2e requête (estimation remesurée) | 6,42 s | 3 |

Les deux requêtes restent sous les 8 s du front : la mémoire validée s'affiche toujours. Avec des textes longs, le moteur ne traduit que 1 à 3 segments par requête. La couverture repose d'autant plus sur le cache, qui accumule les traductions de visite en visite, et sur la mémoire validée par le natif.
