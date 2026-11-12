from flask import current_app, request


def extension_allowed(origin: str) -> bool:
    """Développement : toute extension (l'identifiant d'une extension non empaquetée change) ; production : la liste."""
    allowed = current_app.config["ALLOWED_ORIGINS"]
    return origin.startswith("chrome-extension://") and (not allowed or origin in allowed)


def register_cors(app):
    @app.after_request
    def cors(resp):
        origin = request.headers.get("Origin", "")
        # l'admin n'est jamais appelé par l'extension : pas de CORS
        if request.path.startswith("/v1/admin"):
            return resp
        if extension_allowed(origin):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Accept"
            # sans cette ligne, le front ne peut pas lire l'étiquette « Voix enregistrée »
            resp.headers["Access-Control-Expose-Headers"] = "X-Amira-Voice"
            resp.headers["Access-Control-Max-Age"] = "600"
        return resp
