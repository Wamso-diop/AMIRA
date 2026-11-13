import hmac
import logging
import os
import re
import threading
import time
from collections.abc import Mapping

import click
from flask import Flask, abort, current_app, g, request
from flask.cli import with_appcontext
from werkzeug.middleware.proxy_fix import ProxyFix

from . import config, db, engine as engines
from .cors import extension_allowed, register_cors
from .errors import ApiError, register_errors
from .gold_sync import GoldSync
from .routes.admin import admin, export_admin
from .routes.public import public
from .services.translator import MachineCache

log = logging.getLogger("amira")
RID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")
MAX_JSON = 256 * 1024
_FROM_CONFIG = object()


def create_app(env: Mapping[str, str] | None = None, engine=_FROM_CONFIG) -> Flask:
    """env : variables AMIRA_* (os.environ par défaut). engine : objet avec ready() et translate() ;
    par défaut, celui de la configuration (AMIRA_ENGINE), chargé au premier ready()."""
    app = Flask(__name__)
    app.config.update(config.load(os.environ if env is None else env))
    app.debug = app.config["ENV"] == "development" and app.debug
    if app.config["TRUSTED_PROXIES"]:
        # X-Forwarded-For : seules les n dernières adresses, ajoutées par nos proxys, comptent (le reste est forgeable)
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=app.config["TRUSTED_PROXIES"])
    app.extensions["amira"] = {
        "engine": engines.from_config(app.config) if engine is _FROM_CONFIG else engine,
        "cache": MachineCache(app.config["CACHE_SIZE"], app.config["NEGATIVE_TTL_S"]),
        "gold": GoldSync(app.config["GOLD_PATH"], app.config["GOLD_VALIDATOR"], app.config["TARGET"]),
    }
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
    log.setLevel(logging.INFO)

    # shortcut: limiteur en mémoire, par adresse, pour un seul processus ; derrière la banque, les quotas de la passerelle priment
    buckets: dict[str, tuple[float, float]] = {}
    lock = threading.Lock()

    def rate_limited() -> int | None:
        """Seau à jetons par adresse. Renvoie le délai d'attente en ms, ou None."""
        per_min = app.config["RATE_LIMIT_PER_MIN"]
        rate, now, ip = per_min / 60, time.monotonic(), request.remote_addr or "?"
        with lock:
            if len(buckets) > 10_000:  # mémoire bornée : on oublie les adresses inactives
                for k in [k for k, (_, last) in buckets.items() if now - last > 60]:
                    del buckets[k]
            tokens, last = buckets.get(ip, (per_min, now))
            tokens = min(per_min, tokens + (now - last) * rate)
            if tokens < 1:
                buckets[ip] = (tokens, now)
                return int((1 - tokens) / rate * 1000) + 1
            buckets[ip] = (tokens - 1, now)
            return None

    @app.before_request
    def limits():
        g.t0 = time.perf_counter()
        # taille : avant toute lecture du corps ; 256 Ko pour du JSON, 5 Mo pour l'audio
        limit = MAX_JSON if request.mimetype == "application/json" else app.config["MAX_CONTENT_LENGTH"]
        request.max_content_length = limit  # couvre aussi un corps envoyé sans Content-Length
        if (request.content_length or 0) > limit:
            abort(413)
        if request.endpoint in ("public.health", "public.ready"):
            return  # supervision
        wait = rate_limited()
        if wait is not None:
            raise ApiError("RATE_LIMITED", "Trop de requêtes", status=429, retry_after_ms=wait)
        # appels serveur-à-serveur : clé obligatoire si AMIRA_API_KEYS est défini (l'admin a son propre jeton)
        keys = app.config["API_KEYS"]
        if keys and request.blueprint == "public" and not extension_allowed(request.headers.get("Origin", "")):
            given = request.headers.get("X-Amira-Key", "").encode()
            ok = False
            for key in keys:
                ok |= hmac.compare_digest(given, key.encode())
            if not given or not ok:
                raise ApiError("BAD_REQUEST", "Clé d'API requise", status=401)

    @app.after_request
    def headers_and_log(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Cache-Control"] = "no-store"
        # une ligne par requête : jamais de texte, ni de corps, ni de query string
        ms = round((time.perf_counter() - g.get("t0", time.perf_counter())) * 1000)
        rid = g.get("request_id")
        rid = rid if isinstance(rid, str) and RID_RE.fullmatch(rid) else "-"
        stats = " ".join(f"{k}={v}" for k, v in g.get("stats", {}).items())
        log.info("%s %s %s %sms rid=%s%s", request.method, request.path, resp.status_code, ms, rid, " " + stats if stats else "")
        return resp

    register_cors(app)
    register_errors(app)
    app.register_blueprint(public, url_prefix="/v1")
    app.register_blueprint(admin, url_prefix="/v1/admin")
    app.cli.add_command(export_admin)
    app.cli.add_command(purge)
    return app


@click.command("purge")
@with_appcontext
def purge():
    """Supprime les signalements en attente et les textes « unmatched » plus vieux que AMIRA_RETENTION_DAYS (90)."""
    days = current_app.config["RETENTION_DAYS"]
    fb, um = db.purge(db.connect(current_app.config["DB_PATH"]), days)
    click.echo(f"purge ({days} jours) : {fb} signalements en attente, {um} textes non reconnus")
