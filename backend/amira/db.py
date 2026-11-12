"""SQLite par sqlite3, requêtes paramétrées uniquement, SQL standard (portable vers PostgreSQL).
Tous les textes stockés sont masqués et ont passé la garde."""
import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone

from .markers import canonicalize

SCHEMA = """
CREATE TABLE IF NOT EXISTS translations (
  source TEXT NOT NULL, target TEXT NOT NULL, variety TEXT NOT NULL, key TEXT NOT NULL,
  source_masked TEXT NOT NULL, text TEXT NOT NULL, kind TEXT,
  validated_by TEXT NOT NULL, ref TEXT, updated_at TEXT NOT NULL,
  PRIMARY KEY (source, target, variety, key)
);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY, segment_id TEXT, original_masked TEXT, shown TEXT, suggestion TEXT,
  status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS unmatched (
  source TEXT NOT NULL, target TEXT NOT NULL, variety TEXT NOT NULL, key TEXT NOT NULL,
  text_masked TEXT NOT NULL, requests INTEGER NOT NULL DEFAULT 1, last_at TEXT NOT NULL,
  PRIMARY KEY (source, target, variety, key)
);
CREATE TABLE IF NOT EXISTS recordings (
  segment_key TEXT NOT NULL, language TEXT NOT NULL, path TEXT NOT NULL, mime TEXT NOT NULL,
  speaker TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (segment_key, language)
);
CREATE TABLE IF NOT EXISTS missing_audio (
  segment_key TEXT NOT NULL, language TEXT NOT NULL, text TEXT NOT NULL,
  requests INTEGER NOT NULL DEFAULT 1, last_at TEXT NOT NULL, PRIMARY KEY (segment_key, language)
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, who TEXT NOT NULL, action TEXT NOT NULL, key TEXT
);
CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL);
"""
# shortcut: « id INTEGER PRIMARY KEY » est l'auto-incrément de SQLite ; en PostgreSQL : GENERATED ALWAYS AS IDENTITY.

TRAILING_PUNCT_RE = re.compile(r"[\s.!?:;,…]+$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def memory_key(masked: str) -> str:
    """Clé de mémoire : {N} renumérotés, NFC, minuscules, espaces simples, ponctuation finale retirée.
    Les repères {B}/{E} sont gardés : un texte balisé n'est servi que par une entrée qui a les mêmes repères."""
    canon, _ = canonicalize(masked)
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFC", canon)).strip().lower()
    # les marqueurs gardent leur casse ({N0}, pas {n0})
    text = re.sub(r"\{(/?)([nbe])(\d+)\}", lambda m: "{" + m.group(1) + m.group(2).upper() + m.group(3) + "}", text)
    return TRAILING_PUNCT_RE.sub("", text)


def find_translation(conn, source: str, target: str, variety: str, key: str):
    return conn.execute(
        "SELECT source_masked, text, kind FROM translations WHERE source = ? AND target = ? AND variety = ? AND key = ?",
        (source, target, variety, key),
    ).fetchone()


def note_unmatched(conn, source: str, target: str, variety: str, key: str, text: str) -> None:
    """Texte sensible demandé sans traduction validée : la liste que les natifs valident en priorité."""
    conn.execute(
        "INSERT INTO unmatched (source, target, variety, key, text_masked, requests, last_at) VALUES (?, ?, ?, ?, ?, 1, ?) "
        "ON CONFLICT (source, target, variety, key) DO UPDATE SET requests = unmatched.requests + 1, last_at = excluded.last_at",
        (source, target, variety, key, text, now()),
    )
    conn.commit()


def audit(conn, who: str, action: str, key: str | None = None) -> None:
    conn.execute("INSERT INTO audit (at, who, action, key) VALUES (?, ?, ?, ?)", (now(), who, action, key))


def bump(conn, name: str) -> None:
    conn.execute(
        "INSERT INTO counters (name, value) VALUES (?, 1) ON CONFLICT (name) DO UPDATE SET value = counters.value + 1",
        (name,),
    )
    conn.commit()


def counter(conn, name: str) -> int:
    row = conn.execute("SELECT value FROM counters WHERE name = ?", (name,)).fetchone()
    return row[0] if row else 0


def purge(conn, days: int) -> tuple[int, int]:
    """Rétention : signalements en attente et textes « unmatched » plus vieux que `days` jours. Renvoie (feedback, unmatched)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    with conn:
        fb = conn.execute("DELETE FROM feedback WHERE status = 'pending' AND created_at < ?", (cutoff,)).rowcount
        um = conn.execute("DELETE FROM unmatched WHERE last_at < ?", (cutoff,)).rowcount
        audit(conn, "systeme", "purge", f"feedback={fb} unmatched={um} jours={days}")
    return fb, um
