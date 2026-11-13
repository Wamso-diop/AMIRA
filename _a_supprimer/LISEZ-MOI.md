# À supprimer

Tout ce qui est ici a été **déplacé, pas détruit**, pendant la réorganisation. Rien dans le projet n'en dépend (tests et build vérifiés).
Pour supprimer définitivement : effacer ce dossier. Pour restaurer un élément : le remettre à son emplacement d'origine.

| Dossier | Emplacement d'origine | Pourquoi |
|---|---|---|
| `enregistrements_bruts/` | `backend/data/Voice recording/` | Enregistrements d'origine du locuteur. Chacun a une copie identique (vérifiée par empreinte) rangée dans `backend/languages/ff/audio/`. |
| `docker/` | `backend/Dockerfile`, `docker-compose.yml`, `.dockerignore` | Docker n'est plus utilisé (jamais construit ni testé). |
| `process_dev/` | `backend/BRIEF.md`, `backend/tasks/` | Consignes de travail et suivi interne, inutiles au jury. |

Fichiers parasites déjà supprimés de `backend/` (ils venaient d'une redirection de shell ratée, et étaient vides) : `en`, `ff,en`, `ff,ff`, `fr,ff`.

Les mentions de ces éléments dans les documents (`SPEC.md`, `CONSTRAINTS.md`) restent des références historiques.
