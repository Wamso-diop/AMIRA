# Back-end Amira

API Flask qui traduit des textes **masqués** entre fr/en et fulfulde : mémoire validée par un natif d'abord, modèle NLLB local ensuite.

1. **Installer** : `python3 -m venv .venv && .venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch==2.15.0 && .venv/bin/pip install -r requirements-dev.txt -c constraints.txt`
2. **Configurer** : modèle dans `models/nllb_ff/`, puis `cp .env.example .env` (renseigner `AMIRA_ADMIN_TOKENS`).
3. **Charger la mémoire** : `.venv/bin/python -m tools.import_gold data/gold_fulfulde.csv --validator natif-1`
4. **Lancer** : `.venv/bin/gunicorn -w 1 --threads 4 -b 127.0.0.1:5000 wsgi:app` (ou `docker compose up`, voir [docs/EXPLOITATION.md](docs/EXPLOITATION.md)).
5. **Tester** : `.venv/bin/pytest` ; vrai modèle : `pytest -m model` ; bout en bout avec l'extension : `bash tools/e2e_extension.sh`.
6. **Brancher le front** : `cd ../front && VITE_AMIRA_API_URL=http://localhost:5000 npm run build`, puis ↻ sous Amira dans `chrome://extensions` : la pastille passe à « Prêt ».

Contrat : [docs/openapi.yaml](docs/openapi.yaml) · Règles : [CONSTRAINTS.md](CONSTRAINTS.md) · Spec : [SPEC.md](SPEC.md) · Masquage : [docs/MASQUAGE.md](docs/MASQUAGE.md) · Mesures : [docs/PERF.md](docs/PERF.md) · Licences : [LICENSES.md](LICENSES.md) · Conception initiale : [docs/CONCEPTION.md](docs/CONCEPTION.md)
