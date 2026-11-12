import time

from flask import Blueprint, current_app, g, request

from .. import db
from ..errors import ApiError
from ..services import translator

public = Blueprint("public", __name__)

MAX_SEGMENTS, MAX_CHARS = 40, 1000


def get_db():
    if "db" not in g:
        g.db = db.connect(current_app.config["DB_PATH"])
    return g.db


@public.teardown_app_request
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def _json() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("BAD_REQUEST", "Corps JSON attendu")
    return data


@public.get("/health")
def health():
    return {"ok": True, "version": current_app.config["ENGINE_VERSION"]}


@public.get("/ready")
def ready():
    engine = current_app.extensions["amira"]["engine"]
    if engine is None or not engine.ready():
        raise ApiError("UNAVAILABLE", "Modèle en cours de chargement", status=503)
    get_db().execute("SELECT 1")
    return {"ok": True, "version": current_app.config["ENGINE_VERSION"]}


@public.get("/capabilities")
def capabilities():
    cfg = current_app.config
    return {
        "translate": True,
        "tts": cfg["TTS_ENABLED"],
        "stt": cfg["STT_ENABLED"],
        "languages": cfg["LANGUAGES"],
        "varietes": cfg["VARIETIES"],
    }


@public.post("/translate")
def translate():
    t0 = time.perf_counter()
    cfg = current_app.config
    req = _json()

    raw = req.get("segments")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_SEGMENTS:
        raise ApiError("BAD_REQUEST", f"Entre 1 et {MAX_SEGMENTS} segments par requête")
    segments = []
    for s in raw:
        if not isinstance(s, dict) or not isinstance(s.get("id"), str) or not isinstance(s.get("text"), str):
            raise ApiError("BAD_REQUEST", "Segment mal formé : id et text attendus")
        if len(s["text"]) > MAX_CHARS:
            raise ApiError("BAD_REQUEST", f"Segment trop long ({MAX_CHARS} caractères au plus)")
        hint = s.get("categoryHint")
        category = hint if isinstance(hint, str) and hint in translator.CATEGORIES else None
        segments.append({"id": s["id"], "text": s["text"], "category": category})

    source, target = req.get("source"), req.get("target")
    if source == "auto":
        # détection sur les seuls textes qui passent la garde
        source = translator.detect([s["text"] for s in segments if translator.check(s["text"])])
    if f"{source}>{target}" not in cfg["DIRECTIONS"]:
        raise ApiError("UNSUPPORTED_LANGUAGE", "Sens de traduction non pris en charge")

    # la variété ne compte que vers le fulfulde (l'extension envoie toujours « ngaoundere »)
    variety = ""
    if target == "ff":
        variety = req.get("variety") or cfg["VARIETIES"][0]
        if variety not in cfg["VARIETIES"]:
            raise ApiError("BAD_REQUEST", "Variété inconnue")

    out = translator.translate_segments(get_db(), segments, source, target, variety)
    request_id = req.get("requestId")
    return {
        "requestId": request_id if isinstance(request_id, str) else "",
        "engineVersion": cfg["ENGINE_VERSION"],
        "latencyMs": round((time.perf_counter() - t0) * 1000),
        "segments": out,
    }
