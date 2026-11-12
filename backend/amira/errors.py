"""Toute erreur a la forme attendue par le front : {"error": {"code", "message", "retryAfterMs"?}}."""
import logging
import traceback

from flask import jsonify
from werkzeug.exceptions import HTTPException

log = logging.getLogger("amira")


class ApiError(Exception):
    """Codes lus par le front : RATE_LIMITED, UNAVAILABLE, TIMEOUT, BAD_REQUEST, UNSUPPORTED_LANGUAGE.
    Le message est fixe, écrit par nous : jamais de texte utilisateur."""

    def __init__(self, code: str, message: str, status: int = 400, retry_after_ms: int | None = None):
        super().__init__(code)
        self.code, self.message, self.status, self.retry_after_ms = code, message, status, retry_after_ms


def body(code: str, message: str, retry_after_ms: int | None = None):
    err = {"code": code, "message": message[:200]}
    if retry_after_ms is not None:
        err["retryAfterMs"] = retry_after_ms
    return jsonify({"error": err})


HTTP_MESSAGES = {404: "Point d'accès inconnu", 405: "Méthode non autorisée", 413: "Requête trop volumineuse"}


def register_errors(app):
    @app.errorhandler(ApiError)
    def api_error(e: ApiError):
        return body(e.code, e.message, e.retry_after_ms), e.status

    @app.errorhandler(HTTPException)
    def http_error(e: HTTPException):
        code = "RATE_LIMITED" if e.code == 429 else "UNAVAILABLE" if e.code >= 500 else "BAD_REQUEST"
        return body(code, HTTP_MESSAGES.get(e.code, "Requête invalide")), e.code

    @app.errorhandler(Exception)
    def unexpected(e: Exception):
        # type et emplacement seulement : le message d'une exception peut contenir du texte utilisateur
        frame = traceback.extract_tb(e.__traceback__)[-1] if e.__traceback__ else None
        where = f"{frame.filename.rsplit('/', 1)[-1]}:{frame.lineno}" if frame else "?"
        log.error("erreur interne %s à %s", type(e).__name__, where)
        return body("UNAVAILABLE", "Service momentanément indisponible"), 500
