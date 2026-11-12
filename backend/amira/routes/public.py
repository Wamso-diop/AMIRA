import re
import time

from flask import Blueprint, Response, current_app, g, request, send_file

from .. import db
from ..errors import ApiError
from ..guard import check
from ..markers import speakable
from ..services import translator, voice

public = Blueprint("public", __name__)

MAX_SEGMENTS, MAX_CHARS = 40, 1000
ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")


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
    if current_app.config["ENGINE"] != "memory" and (engine is None or not engine.ready()):
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

    out = translator.translate_segments(get_db(), segments, source, target, variety,
                                        current_app.extensions["amira"]["engine"], cfg, t0)
    request_id = req.get("requestId")
    return {
        "requestId": request_id if isinstance(request_id, str) else "",
        "engineVersion": cfg["ENGINE_VERSION"],
        "latencyMs": round((time.perf_counter() - t0) * 1000),
        "segments": out,
    }


@public.post("/tts")
def tts():
    cfg = current_app.config
    if not cfg["TTS_ENABLED"]:
        raise ApiError("BAD_REQUEST", "Voix désactivée")
    req = _json()
    text, language, key, speed = req.get("text"), req.get("language"), req.get("segmentKey"), req.get("speed", 1)
    if not isinstance(text, str) or len(text) > MAX_CHARS or language not in cfg["LANGUAGES"]:
        raise ApiError("BAD_REQUEST", "Texte ou langue invalide")
    if key is not None and not (isinstance(key, str) and voice.KEY_RE.fullmatch(key)):
        raise ApiError("BAD_REQUEST", "segmentKey invalide")
    if isinstance(speed, bool) or not isinstance(speed, (int, float)):
        raise ApiError("BAD_REQUEST", "speed invalide")
    text = speakable(text)
    if not text:
        raise ApiError("BAD_REQUEST", "Texte vide")
    conn = get_db()
    # garde : rien n'est stocké, la réponse ne dit pas pourquoi
    if not check(text):
        db.bump(conn, "unmasked_total")
        return "", 204
    # 1. enregistrement d'un locuteur natif pour ce passage
    if key:
        rec = voice.find_recording(conn, key, language)
        if rec:
            resp = send_file(rec["path"], mimetype=rec["mime"], conditional=False)
            resp.headers["X-Amira-Voice"] = "recorded"
            return resp
        # 2. passage demandé sans enregistrement : il entre dans la liste « à enregistrer »
        voice.note_missing(conn, key, language, text)
    # 3. voix de synthèse du serveur, si elle existe un jour pour cette langue
    audio = voice.synthesize(text, language, float(speed))
    if audio:
        data, mime = audio
        return Response(data, mimetype=mime, headers={"X-Amira-Voice": "synthetic"})
    # 4. rien : le panneau lit avec la voix du navigateur
    return "", 204


@public.post("/stt")
def stt():
    raise ApiError("BAD_REQUEST", "Dictée désactivée")  # capabilities annonce stt: false


@public.post("/feedback")
def feedback():
    req = _json()
    fields = ("originalMasked", "shown", "suggestion")
    if not (isinstance(req.get("segmentId"), str) and ID_RE.fullmatch(req["segmentId"])):
        raise ApiError("BAD_REQUEST", "segmentId invalide")
    if not all(isinstance(req.get(f), str) and len(req[f]) <= MAX_CHARS for f in fields):
        raise ApiError("BAD_REQUEST", "originalMasked, shown et suggestion attendus (1000 caractères au plus)")
    conn = get_db()
    # garde : un signalement qui contient une donnée réelle n'est pas stocké
    if not all(check(req[f]) for f in fields):
        db.bump(conn, "unmasked_total")
        return "", 204
    # file de relecture seulement : jamais une entrée « validated » (seul l'admin en crée)
    conn.execute(
        "INSERT INTO feedback (segment_id, original_masked, shown, suggestion, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
        (req["segmentId"], req["originalMasked"], req["shown"], req["suggestion"], db.now()),
    )
    conn.commit()
    return "", 204
