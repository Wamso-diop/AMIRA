# Mesures de performance

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

## S10 : lot de 40, mémoire et moteur (2026-11-12)

Commande : `pytest -m model -s tests/test_perf.py`. Même machine ; budget 6 s, paquets de 4, 0,8 s estimées par segment.

| Mesure | Valeur |
|---|---|
| Lot de 40 (20 du gold + 20 phrases inconnues), 5 essais | médiane **3,55 s**, p95 **3,77 s** |
| Statuts, à chaque essai | 20 `validated`, 4 `machine`, 16 `uncertain` |
| 4 requêtes simultanées (lots différents) | 3,57 s / 2,81 s / 2,81 s / 2,81 s ; segments `machine` : 4 / 0 / 0 / 0 |
| Premier appel puis suivant (après l'échauffement) | 1,91 s puis 1,59 s |

### Lecture

- **Latence tenue** : p95 de 3,8 s, sous les 6 s du budget et les 8 s du front. Les mesures de secours du brief (cache, CTranslate2) ne sont donc pas déclenchées par la latence. De toute façon, CTranslate2 demande de **convertir** le modèle, ce que le brief interdit (§5).
- **Couverture limitée** : un paquet de 4 segments prend environ 3,5 s, donc le paquet suivant ne tient jamais dans le budget. Au-delà de la mémoire, **4 segments par requête** passent par le moteur, toujours les 4 premiers. Ceux qui reviennent `uncertain` sont redemandés à la visite suivante, et redonnent les mêmes 4 : sans cache côté serveur, une page qui a plus de 4 textes inconnus n'en verra jamais plus de 4 traduits.
- **Requêtes simultanées** : le modèle ne traite qu'une génération à la fois (un seul en RAM). Les requêtes qui attendent rendent la main avant les 8 s, avec des segments `uncertain`. Rien ne bloque, mais un seul utilisateur à la fois profite du moteur.
- **Échauffement** : la phrase traduite pendant le chargement ne change presque rien (1,9 s contre 1,6 s, comme avant l'échauffement) ; l'écart vient de la phrase, pas d'un démarrage à froid.
