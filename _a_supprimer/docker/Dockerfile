# Image de production : un seul worker gunicorn (le modèle n'est chargé qu'une fois en RAM, ~3,8 Go), des threads.
# Le modèle n'est PAS dans l'image : il est monté en lecture seule sur /models/nllb_ff (voir docker-compose.yml).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    AMIRA_DB_PATH=/data/amira.sqlite3 AMIRA_RECORDINGS_DIR=/data/recordings AMIRA_MODEL_DIR=/models/nllb_ff \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/tmp/hf

WORKDIR /app
COPY requirements.txt constraints.txt ./
# pip et setuptools à jour (les versions livrées ont des vulnérabilités connues) ; torch CPU depuis l'index PyTorch
RUN pip install --upgrade pip setuptools \
 && pip install --index-url https://download.pytorch.org/whl/cpu torch==2.15.0 \
 && pip install -r requirements.txt -c constraints.txt

COPY amira ./amira
COPY tools/__init__.py tools/import_gold.py ./tools/
COPY wsgi.py ./
COPY languages ./languages

# utilisateur sans droits ; seul /data (volume) est inscriptible
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin amira && mkdir /data && chown amira /data
USER amira

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=60s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/v1/ready', timeout=2)"

# l'import du gold est idempotent : il remet la mémoire à jour à chaque démarrage, sans toucher aux entrées admin
CMD ["sh", "-c", "python -m tools.import_gold languages/${AMIRA_LANGUAGE:-ff}/gold.csv --validator \"${AMIRA_GOLD_VALIDATOR:-natif-1}\" && exec gunicorn -w 1 --threads 4 -b 0.0.0.0:8000 --timeout 30 wsgi:app"]
