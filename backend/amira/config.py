"""Configuration : variables d'environnement uniquement (voir .env.example)."""
import ipaddress
import json
from collections.abc import Mapping
from pathlib import Path

LANGUAGES_DIR = Path(__file__).parents[1] / "languages"


def _list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def load_language(code: str) -> dict:
    """Fiche de la langue cible : languages/<code>/language.json (voir languages/README.md pour en ajouter une)."""
    path = LANGUAGES_DIR / code / "language.json"
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
        return {k: info[k] for k in ("code", "name", "varieties", "model_dir", "engine_version")}
    except (OSError, ValueError, KeyError):
        raise RuntimeError(f"AMIRA_LANGUAGE={code} : fiche languages/{code}/language.json absente ou incomplète") from None


def load(env: Mapping[str, str]) -> dict:
    def get(name: str, default: str = "") -> str:
        return env.get(name, default)

    # une installation sert une langue cible ; tout ce qui en dépend (modèle, mémoire, sens) en est déduit, sauf surcharge par AMIRA_*
    lang = load_language(get("AMIRA_LANGUAGE", "ff"))
    c = lang["code"]

    cfg = {
        "ENV": get("AMIRA_ENV", "production"),
        "ALLOWED_ORIGINS": _list(get("AMIRA_ALLOWED_ORIGINS")),
        "ENGINE_VERSION": get("AMIRA_ENGINE_VERSION", lang["engine_version"]),
        "TTS_ENABLED": get("AMIRA_TTS_ENABLED", "true").lower() == "true",
        "STT_ENABLED": get("AMIRA_STT_ENABLED", "false").lower() == "true",
        "TARGET": c,
        "LANGUAGES": _list(get("AMIRA_LANGUAGES", f"fr,en,{c}")),
        "VARIETIES": _list(get("AMIRA_VARIETIES", ",".join(lang["varieties"]))),
        # sens autorisés : jamais fr↔en
        "DIRECTIONS": _list(get("AMIRA_DIRECTIONS", f"fr>{c},en>{c},{c}>fr,{c}>en")),
        "DB_PATH": get("AMIRA_DB_PATH", "data/amira.sqlite3"),
        # moteur : m2m100 (modèle local) ou memory (mémoire validée seule)
        "ENGINE": get("AMIRA_ENGINE", "m2m100"),
        "MODEL_DIR": get("AMIRA_MODEL_DIR", lang["model_dir"]),
        "LANG_CODES": dict(p.split("=", 1) for p in _list(get("AMIRA_LANG_CODES", f"fr=fr,en=en,{c}={c}"))),
        "MIN_CONFIDENCE": float(get("AMIRA_MIN_CONFIDENCE", "0.5")),
        "MIN_CONFIDENCE_FROM_FF": float(get("AMIRA_MIN_CONFIDENCE_FROM_FF", "0.7")),
        "ENGINE_BUDGET_S": float(get("AMIRA_ENGINE_BUDGET_S", "6")),
        "ENGINE_BATCH": int(get("AMIRA_ENGINE_BATCH", "4")),
        # estimation de départ ; le moteur la remesure après chaque génération
        "ENGINE_SEG_S": float(get("AMIRA_ENGINE_SEG_S", "0.8")),
        # outils des natifs : plusieurs jetons pour la rotation (ajouter le nouveau, puis retirer l'ancien)
        "ADMIN_TOKENS": _list(get("AMIRA_ADMIN_TOKENS")),
        "ADMIN_NETWORKS": _list(get("AMIRA_ADMIN_NETWORKS", "127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16")),
        # derrière la passerelle : nombre de proxys de confiance devant le service (0 = X-Forwarded-For ignoré)
        "TRUSTED_PROXIES": get("AMIRA_TRUSTED_PROXIES", "0"),
        "RECORDINGS_DIR": get("AMIRA_RECORDINGS_DIR", "media/recordings"),
        # cache des sorties machine (mémoire vive) : taille LRU et durée du cache négatif
        "CACHE_SIZE": int(get("AMIRA_CACHE_SIZE", "10000")),
        "NEGATIVE_TTL_S": float(get("AMIRA_NEGATIVE_TTL_S", "600")),
        "API_KEYS": _list(get("AMIRA_API_KEYS")),
        "RATE_LIMIT_PER_MIN": int(get("AMIRA_RATE_LIMIT_PER_MIN", "600")),
        # CSV gold rechargé dès qu'il change (vide : import à la main seulement, par tools.import_gold)
        "GOLD_PATH": get("AMIRA_GOLD_PATH", f"languages/{c}/gold.csv"),
        "GOLD_VALIDATOR": get("AMIRA_GOLD_VALIDATOR"),
        "RETENTION_DAYS": int(get("AMIRA_RETENTION_DAYS", "90")),
        "MAX_CONTENT_LENGTH": 5 * 1024 * 1024,
    }
    # validés au démarrage : une faute de frappe ne doit pas casser l'admin à la première connexion
    try:
        cfg["ADMIN_NETWORKS"] = [ipaddress.ip_network(n, strict=False) for n in cfg["ADMIN_NETWORKS"]]
    except ValueError:
        raise RuntimeError("AMIRA_ADMIN_NETWORKS : réseau invalide (exemple : 10.0.0.0/8)") from None
    if not cfg["TRUSTED_PROXIES"].isdigit():
        raise RuntimeError("AMIRA_TRUSTED_PROXIES : nombre entier de proxys de confiance (0 par défaut)")
    cfg["TRUSTED_PROXIES"] = int(cfg["TRUSTED_PROXIES"])
    if cfg["ENGINE"] not in ("m2m100", "memory"):
        raise RuntimeError("AMIRA_ENGINE vaut m2m100 ou memory")
    if cfg["ENV"] != "development" and not cfg["ALLOWED_ORIGINS"]:
        raise RuntimeError("AMIRA_ALLOWED_ORIGINS est obligatoire hors développement (identifiant de l'extension publiée)")
    return cfg
