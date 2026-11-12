import os
from collections.abc import Mapping

from flask import Flask, abort, request

from . import config
from .cors import register_cors
from .errors import register_errors
from .routes.public import public


def create_app(env: Mapping[str, str] | None = None, engine=None) -> Flask:
    """env : variables AMIRA_* (os.environ par défaut). engine : objet avec ready() et translate()."""
    app = Flask(__name__)
    app.config.update(config.load(os.environ if env is None else env))
    app.debug = app.config["ENV"] == "development" and app.debug
    app.extensions["amira"] = {"engine": engine}

    @app.before_request
    def too_large():
        # avant toute lecture du corps, quel que soit le point d'accès
        if (request.content_length or 0) > app.config["MAX_CONTENT_LENGTH"]:
            abort(413)

    register_cors(app)
    register_errors(app)
    app.register_blueprint(public, url_prefix="/v1")
    return app
