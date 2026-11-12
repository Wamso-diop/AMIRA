"""Chaîne d'un segment : garde → mémoire validée → catégorie sensible → (moteur, S6) → incertain."""
import hashlib
import logging
import re

from .. import db
from ..guard import check
from ..markers import canonicalize, markers_ok, restore

log = logging.getLogger("amira")

SENSITIVE = {"security_warning", "fees"}
CATEGORIES = {"label", "instruction", "fees", "security_warning", "error"}

# Détection minimale pour source « auto » (l'extension ne l'envoie plus) : mots outils comptés sur tout le lot.
FR_WORDS = set("le la les de des du et est votre vous pour une un au aux sur avec pas ne ce cette doit être".split())
EN_WORDS = set("the of and is your you for a an to in on with not this that must be are please".split())


def detect(texts: list[str]) -> str | None:
    words = re.findall(r"[a-zà-ÿ]+", " ".join(texts).lower())
    fr, en = sum(w in FR_WORDS for w in words), sum(w in EN_WORDS for w in words)
    return "fr" if fr > en else "en" if en > fr else None


def uncertain(seg_id: str, text: str) -> dict:
    """P5 : dans le doute, le texte source tel que reçu ; le front garde l'original."""
    return {"id": seg_id, "text": text, "status": "uncertain", "confidence": 0.0, "origin": "llm"}


def translate_segments(conn, segments: list[dict], source: str, target: str, variety: str) -> list[dict]:
    """segments : [{"id", "text", "category"}] déjà validés en forme. variety : '' si la cible n'est pas ff."""
    out = []
    for s in segments:
        seg_id, text = s["id"], s["text"]
        # 1. garde : un texte refusé n'est ni cherché, ni transmis, ni stocké, ni journalisé
        if not check(text):
            db.bump(conn, "unmasked_total")
            out.append(uncertain(seg_id, text))
            continue
        key = db.memory_key(text)
        # 2. mémoire validée par un natif
        hit = db.find_translation(conn, source, target, variety, key)
        if hit:
            _, table = canonicalize(text)
            translated = restore(hit["text"], table)
            if markers_ok(text, translated):
                out.append({"id": seg_id, "text": translated, "status": "validated", "confidence": 1.0, "origin": "memory"})
                continue
            db.bump(conn, "memory_bad_markers")
            log.warning("entrée de mémoire ignorée : marqueurs différents (clé %s)", hashlib.sha256(key.encode()).hexdigest()[:12])
        # 3. catégorie sensible sans mémoire : jamais de moteur, liste à faire valider en priorité
        if s["category"] in SENSITIVE:
            db.note_unmatched(conn, source, target, variety, key, text)
        # 4. moteur : S6
        out.append(uncertain(seg_id, text))
    return out
