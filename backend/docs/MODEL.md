# Modèle M2M100 (famille `m2m100`)

Vérifié localement le 2026-11-14, sans accès réseau (le modèle a été déposé à la main ; `HF_HUB_OFFLINE=1`).
Le modèle reste **hors de git** (`backend/models/` est ignoré ; `tools/check_repo.py` refuse tout poids indexé).

## Où le placer

`backend/models/m2m_ff/` (variable `AMIRA_MODEL_DIR`, famille `AMIRA_MODEL_FAMILY=m2m100`).

Fichiers présents : `config.json`, `generation_config.json`, `model.safetensors`, `sentencepiece.bpe.model`,
`vocab.json`, `tokenizer_config.json`, `added_tokens.json`.
**`special_tokens_map.json` est absent et n'est pas nécessaire** : `added_tokens.json` et `tokenizer_config.json` suffisent
(chargement vérifié, jeton `__ff__` = 128026).

## Intégrité

Vérifier avant usage : `sha256sum models/m2m_ff/model.safetensors`

| Fichier | Taille | SHA-256 |
|---|---|---|
| `model.safetensors` | 1 935 681 888 octets | `7e9e762ecc4ef9e684879f57b32a05d6ef068e0984ec86327b65020515e41f25` |

Calculés par `sha256sum` et `stat` sur cette machine.

## Versions

| Paquet | Version |
|---|---|
| transformers | 5.22.2 |
| torch | 2.15.0+cpu |
| sentencepiece | 0.2.3 (roue binaire, installée le 2026-11-14) |
| safetensors | 0.8.0 |

## Contrôles du 2026-11-14

| Contrôle | Résultat |
|---|---|
| Architecture | `M2M100ForConditionalGeneration`, float32, 483 905 536 paramètres |
| Tenseurs dans `model.safetensors` | 509 |
| NaN / Inf dans les tenseurs | 0 / 0 |
| Tokenizer | `M2M100Tokenizer`, 128 104 jetons ; `vocab_size` du modèle 128 112 (8 jetons « madeup » prévus par la config) |
| Jetons de langue | `__fr__`, `__en__`, `__ff__` valides (`__ff__` = 128026) |
| Lettres du gold ff (ɓ ɗ ƴ ŋ et majuscules) | aucune inconnue du tokenizer ; aucune ligne du gold ff ne produit `<unk>` |
| Marqueurs `{V1}`, `{V2}` | conservés, sortie non vide |
| Contrôle croisé avec la référence Colab (`tests/fixtures/m2m_colab_reference.csv`, 56 phrases, fr et en → ff) | **56 sur 56 identiques** à la colonne `m2m100` : aucune différence |
| Contrôle humain : sortie == colonne `reference` | 13 sur 56 (identique pour Colab et pour ce serveur) |

Le fichier de référence Colab est fourni par l'équipe et **n'est pas commité** (`.gitignore`).

## Référence d'intégrité de cette machine

`python -m tools.check_model --model models/m2m_ff` (avec `AMIRA_MODEL_FAMILY=m2m100`) enregistre, au premier chargement
réussi, la sortie du modèle pour une phrase de contrôle dans `models/m2m_ff/integrity.json`, avec la date
(2026-11-14 ici). Les passages suivants la comparent. Ce fichier est propre à la machine et hors git.

## Licence

À documenter en phase D (`LICENSES.md`).
