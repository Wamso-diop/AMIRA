"""Configuration : variables d'environnement uniquement (voir .env.example)."""
from collections.abc import Mapping


def _list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def load(env: Mapping[str, str]) -> dict:
    def get(name: str, default: str = "") -> str:
        return env.get(name, default)

    cfg = {
        "ENV": get("AMIRA_ENV", "production"),
        "ALLOWED_ORIGINS": _list(get("AMIRA_ALLOWED_ORIGINS")),
        "ENGINE_VERSION": get("AMIRA_ENGINE_VERSION", "amira-nllb-ff-stage2"),
        "TTS_ENABLED": get("AMIRA_TTS_ENABLED", "true").lower() == "true",
        "STT_ENABLED": get("AMIRA_STT_ENABLED", "false").lower() == "true",
        "LANGUAGES": _list(get("AMIRA_LANGUAGES", "fr,en,ff")),
        "VARIETIES": _list(get("AMIRA_VARIETIES", "ngaoundere,garoua,maroua")),
        # sens autorisés : jamais fr↔en ; ajouter une langue = un modèle, une mémoire et cette liste
        "DIRECTIONS": _list(get("AMIRA_DIRECTIONS", "fr>ff,en>ff,ff>fr,ff>en")),
        "DB_PATH": get("AMIRA_DB_PATH", "data/amira.sqlite3"),
        "MAX_CONTENT_LENGTH": 5 * 1024 * 1024,
    }
    if cfg["ENV"] != "development" and not cfg["ALLOWED_ORIGINS"]:
        raise RuntimeError("AMIRA_ALLOWED_ORIGINS est obligatoire hors développement (identifiant de l'extension publiée)")
    return cfg
