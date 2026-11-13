"""Voix : enregistrement d'un natif pour un passage (segmentKey), sinon rien (204, voix du navigateur)."""
import re
from pathlib import Path

from .. import db
from .translator import TAIL_RE

# \s de JavaScript, exactement (celui de Python n'a pas \ufeff et a \x1c-\x1f en plus)
JS_SPACE = "\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
KEY_RE = re.compile(r"k[0-9a-f]{8}")


def segment_key(masked_source: str) -> str:
    """Identique à segmentKey() de front/src/content/engine.ts : FNV-1a 32 bits sur les unités UTF-16."""
    s = re.sub(r"\{/?[BE]\d+\}", " ", masked_source)
    # après réduction, seuls des " " restent aux bords ; str.strip() enlèverait aussi \x1c-\x1f, que trim() de JS garde
    s = re.sub(f"[{JS_SPACE}]+", " ", s).strip(" ").lower()
    data = s.encode("utf-16-le")
    h = 0x811C9DC5
    for i in range(0, len(data), 2):
        h ^= data[i] | (data[i + 1] << 8)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"k{h:08x}"


def audio_key(masked_source: str) -> str:
    """Clé de l'enregistrement : celle du début quand la fin n'est que numéros masqués, codes et ponctuation
    (« Numéro de compte : CM {N0} » est lu comme « Numéro de compte »). Identique à audioKey() du front."""
    tail = TAIL_RE.search(masked_source)
    if tail and tail.start() > 0 and "{N" in tail.group():
        masked_source = masked_source[:tail.start()]
    return segment_key(masked_source)


def find_recording(conn, key: str, language: str):
    row = conn.execute("SELECT path, mime FROM recordings WHERE segment_key = ? AND language = ?", (key, language)).fetchone()
    return row if row and Path(row["path"]).is_file() else None


def note_missing(conn, key: str, language: str, text: str) -> None:
    """Passage demandé sans enregistrement : les plus demandés sont à enregistrer en priorité."""
    conn.execute(
        "INSERT INTO missing_audio (segment_key, language, text, requests, last_at) VALUES (?, ?, ?, 1, ?) "
        "ON CONFLICT (segment_key, language) DO UPDATE SET requests = missing_audio.requests + 1, "
        "text = excluded.text, last_at = excluded.last_at",
        (key, language, text, db.now()),
    )
    conn.commit()


def synthesize(text: str, language: str, speed: float):
    """Aucune voix de synthèse fulfulde disponible : le navigateur lit avec sa propre voix (« Voix de synthèse »)."""
    return None
