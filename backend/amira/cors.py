from flask import current_app, request


def register_cors(app):
    @app.after_request
    def cors(resp):
        origin = request.headers.get("Origin", "")
        allowed = current_app.config["ALLOWED_ORIGINS"]
        # développement : toute extension (l'identifiant d'une extension non empaquetée change) ; production : la liste
        if origin.startswith("chrome-extension://") and (not allowed or origin in allowed):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Accept"
            # sans cette ligne, le front ne peut pas lire l'étiquette « Voix enregistrée »
            resp.headers["Access-Control-Expose-Headers"] = "X-Amira-Voice"
            resp.headers["Access-Control-Max-Age"] = "600"
        return resp
