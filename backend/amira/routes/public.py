from flask import Blueprint, current_app

from ..errors import ApiError

public = Blueprint("public", __name__)


@public.get("/health")
def health():
    return {"ok": True, "version": current_app.config["ENGINE_VERSION"]}


@public.get("/ready")
def ready():
    engine = current_app.extensions["amira"]["engine"]
    if engine is None or not engine.ready():
        raise ApiError("UNAVAILABLE", "Modèle en cours de chargement", status=503)
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
