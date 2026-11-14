# Licences

## Modèle

| Élément | Licence | Conséquence |
|---|---|---|
| Modèle livré : **M2M100, version 418M** (`facebook/m2m100_418M`, 483 905 536 paramètres), affiné pour le fulfulde | **MIT, vérifiée** ([fiche du modèle](https://huggingface.co/facebook/m2m100_418M)) | **Usage commercial permis, à condition de conserver la mention de la licence** (voir ci-dessous). Le modèle affiné reste hors de git (`docs/MODEL.md`). |
| NLLB-200 (`facebook/nllb-200-distilled-600M`) | CC-BY-NC 4.0 (non commercial) | **Évalué, non livré** : retiré du code et du disque le 2026-11-14 à cause de sa licence non commerciale. |

Le moteur reste interchangeable : un autre dossier dans `AMIRA_MODEL_DIR`, ou un autre `engine.py` qui respecte `translate(textes, src, tgt) -> [(texte, confiance)]`.

### Mention de licence à conserver

Ce produit utilise le modèle **M2M100 (version 418M)**, publié par Meta et distribué sous **licence MIT** : <https://huggingface.co/facebook/m2m100_418M>. La licence MIT autorise l'usage, y compris commercial, la modification et la distribution, **à la condition que l'avis de droit d'auteur et le texte de la licence MIT accompagnent toute copie ou version substantielle** du modèle. Toute redistribution du modèle affiné doit donc joindre cette mention.

## Données d'entraînement

| Étape | Jeu de données | Licence |
|---|---|---|
| Affinage, étape 1 | `FredMike23/french-FULFULDE-ADAMAOUA` (Hugging Face) | **MIT, vérifiée** (information de l'équipe). |
| Affinage, étape 2, et mémoire validée (`languages/ff/gold.csv`) | Textes du document « Environnement de test », traduits et corrigés par le locuteur natif de l'équipe | **Droit d'usage à confirmer par le locuteur natif.** |

Consultés mais **non utilisés** : `ARPRIM/pulaar_fulfulde`, `BayangSouloukna/adamawa-fulfulde-silver-v1`, `abdouaziiz/fulfulde_clean`, Common Voice (`fub`), `stfotso/french-ghomala-bandjoun`, Ewondo-TTS-Dataset (Mozilla).

## Bibliothèques

Relevé avec `pip-licenses --from=mixed` le 2026-11-12 (outil installé le temps du relevé, puis retiré). Versions exactes : `requirements.txt` et `constraints.txt`.

| Bibliothèque | Version | Licence | Usage |
|---|---|---|---|
| Flask | 3.1.3 | BSD-3-Clause | production |
| Werkzeug | 3.1.9 | BSD-3-Clause | production (Flask) |
| Jinja2 | 3.1.6 | BSD | production (Flask) |
| MarkupSafe | 3.0.3 | BSD-3-Clause | production (Flask) |
| itsdangerous | 2.2.0 | BSD | production (Flask) |
| click | 8.5.1 | BSD-3-Clause | production (Flask) |
| blinker | 1.9.0 | MIT | production (Flask) |
| gunicorn | 27.0.0 | MIT | production |
| python-dotenv | 1.2.4 | BSD-3-Clause | production |
| transformers | 5.22.2 | Apache-2.0 | production (`engine.py`) |
| tokenizers | 0.23.3 | Apache-2.0 | production (transformers) |
| safetensors | 0.8.0 | Apache-2.0 | production (transformers) |
| sentencepiece | 0.2.3 | Apache-2.0 | production (tokenizer M2M100) ; installée le 2026-11-14, licence selon la documentation du projet, hors relevé `pip-licenses` du 2026-11-12 |
| huggingface_hub | 2.4.0 | Apache-2.0 | production (transformers ; hors ligne) |
| torch | 2.15.0+cpu | BSD-3-Clause, avec des composants Apache-2.0, MIT, BSL-1.0, ISC, Zlib | production (`engine.py`) |
| numpy | 2.5.4 | BSD-3-Clause, avec des composants 0BSD, MIT, Zlib, CC0-1.0 | production (transformers) |
| pytest | 9.2.0 | MIT | tests seulement |
| PyYAML | 6.0.3 | MIT | tests seulement |
| jsonschema | 4.26.0 | MIT | tests seulement |
| pip-audit | 2.10.1 | Apache-2.0 | audit seulement |

Toutes les bibliothèques ont des licences permissives. Aucune licence de bibliothèque ne bloque un usage commercial ; reste à confirmer le droit d'usage de la mémoire validée.
