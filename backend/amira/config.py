"""Configuration : variables d'environnement uniquement (voir .env.example)."""
import ipaddress
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
        # moteur : nllb (modèle local) ou memory (mémoire validée seule)
        "ENGINE": get("AMIRA_ENGINE", "nllb"),
        "MODEL_DIR": get("AMIRA_MODEL_DIR", "models/nllb_ff"),
        "LANG_CODES": dict(p.split("=", 1) for p in _list(get("AMIRA_LANG_CODES", "fr=fra_Latn,en=eng_Latn,ff=fuv_Latn"))),
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
        "GOLD_PATH": get("AMIRA_GOLD_PATH", "data/gold_fulfulde.csv"),
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
    if cfg["ENGINE"] not in ("nllb", "memory"):
        raise RuntimeError("AMIRA_ENGINE vaut nllb ou memory")
    if cfg["ENV"] != "development" and not cfg["ALLOWED_ORIGINS"]:
        raise RuntimeError("AMIRA_ALLOWED_ORIGINS est obligatoire hors développement (identifiant de l'extension publiée)")
    return cfg
