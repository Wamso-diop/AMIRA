# Tâches : back-end Amira

Une étape = test qui échoue → code → `/review` + `/ponytail-review` → commit → résumé → **attendre « go »**.
Vérification commune à chaque étape : `cd backend && pytest -q` vert, aucun test désactivé.

- [x] **S0. Environnement** (aucun code applicatif)
  - Acceptation : modèle dans `models/nllb_ff/` avec `model.safetensors` (renommage **validé par l'humain**) ; CSV dans `data/` ; `.gitignore` couvre `backend/models/`, la base et `media/` ; `tools/check_model.py` charge le modèle, traduit 5 phrases hors gold, affiche texte, confiance, durée, et compare la phrase de contrôle de Colab ; RAM et latence (1 puis 8 segments) dans `docs/PERF.md`.
  - Vérification : `python tools/check_model.py`.
  - Fichiers : `.gitignore`, `requirements.txt`, `tools/check_model.py`, `docs/PERF.md`.

- [x] **S1. Contrat et squelette**
  - Acceptation : `docs/openapi.yaml` (3.1) écrit d'après `api.ts`, avec `/v1/ready` ; `create_app`, configuration, erreurs `{error:{code,message,retryAfterMs?}}`, CORS `chrome-extension://` avec `X-Amira-Voice` exposé ; `/health`, `/ready`, `/capabilities`.
  - Tests : `test_app.py` (erreurs, 404 JSON, 413, préflight, `ready` 503 puis 200, conformité à openapi).
  - Fichiers : `docs/openapi.yaml`, `amira/__init__.py`, `config.py`, `errors.py`, `cors.py`, `routes/public.py`, `tests/conftest.py`, `tests/openapi_check.py`, `.env.example`, `wsgi.py`.

- [x] **S2. Marqueurs**
  - Acceptation : `same_markers`, `well_nested`, `markers_ok`, `canonicalize`, `model_view`/`from_model`, `speakable`.
  - Tests : `test_markers.py` (imbrication, doublons, renumérotation, aller-retour, ajout ou perte, accolades inconnues).
  - Fichiers : `amira/markers.py`, `tests/test_markers.py`.

- [x] **S3. Garde**
  - Acceptation : `guard.check` ; un segment refusé n'est ni cherché, ni transmis, ni stocké, ni journalisé ; `unmasked_total` augmente.
  - Tests : `test_guard.py` (30 cas ou plus, canari).
  - Fichiers : `amira/guard.py`, `tests/test_guard.py`.

- [ ] **S4. Base et import du gold**
  - Acceptation : schéma (6 tables + `counters`), requêtes paramétrées ; import idempotent, `{Vk}→{N(k-1)}`, 4 sens, variantes, refus, conflits, rapport.
  - Tests : `test_import_gold.py`, `test_no_fulfulde.py`.
  - Fichiers : `amira/db.py`, `tools/import_gold.py`, 2 tests.

- [ ] **S5. Traduction par la mémoire seule**
  - Acceptation : forme → garde → mémoire → sensible vers `unmatched` → sinon `uncertain` ; ordre et `id` conservés ; fr↔en refusé ; variété ; `auto`.
  - Tests : `test_translate_memory.py` (exemples tirés du CSV).
  - Fichiers : `amira/services/translator.py`, `routes/public.py`, test.

- [ ] **S6. Moteur**
  - Acceptation : `engine.py` (NLLB paresseux, un seul chargement, verrou, `model_view`), contrôles de sortie, tentative stricte, seuils 0,5 et 0,7, budget de 6 s, `FakeEngine`.
  - Tests : `test_engine.py` (7 cas avec faux moteur + 1 `model`).
  - Fichiers : `amira/engine.py`, `services/translator.py`, test.

- [ ] **S7. Statuts et catégories sensibles**
  - Acceptation : espion jamais appelé pour `security_warning` et `fees` ; `validated` uniquement depuis la mémoire ; parcours complet validé contre openapi.
  - Tests : `test_status.py`.

- [ ] **S8a. Voix** : `/v1/tts`, `segment_key` (5 paires du front), `note_missing`, `204`. Tests : `test_voice.py`.
- [ ] **S8b. Feedback** : garde puis `pending`, jamais `validated`. Tests : `test_feedback.py`.
- [ ] **S8c. Admin** : jeton (`compare_digest`, rotation), réseaux, audit, listes, `PUT translations`, mémoire CSV/JSON, dépôt d'audio (clé, MIME, taille). Tests : `test_admin.py`.

- [ ] **S9. Sécurité transversale**
  - Acceptation : journaux sans texte, exceptions sans texte, débogage coupé, `socket.connect` interdit, limites, 429, en-têtes, `flask purge`, `AMIRA_API_KEYS`, `pip-audit`.
  - Tests : `test_privacy.py`, `test_offline.py`, `test_limits.py`.

- [ ] **S10. Performance**
  - Acceptation : lot de 40 mixte (médiane et p95) et 4 requêtes simultanées mesurés dans `docs/PERF.md` ; échauffement au démarrage ; cache ou CTranslate2 seulement si nécessaire.
  - Tests : `test_perf.py` (`model`).

- [ ] **S11. Livraison**
  - Acceptation : `Dockerfile` (non root, modèle en lecture seule), `docker-compose.yml` (`internal: true`), README (≤ 10 lignes), `LICENSES.md`, `docs/MASQUAGE.md`, `docs/EXPLOITATION.md`, bout en bout avec l'extension, puis `/code-simplify`, `/ponytail-audit`, `/ponytail-debt`, `/ship`.
