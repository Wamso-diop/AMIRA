"""Chaîne d'un segment : garde → mémoire validée → catégorie sensible → moteur contrôlé → incertain."""
import hashlib
import logging
import re
import time

from .. import db
from ..guard import check
from ..engine import EngineError
from ..markers import canonicalize, from_model, markers_ok, model_view, restore

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


def acceptable(source_text: str, out: str, confidence: float, threshold: float) -> bool:
    """P4 et P5 : sortie du moteur acceptée seulement si tout est vérifié."""
    return (
        bool(out.strip())
        and markers_ok(source_text, out)
        and check(out)  # aucun chiffre, devise ni e-mail ajouté par le moteur
        and db.memory_key(out) != db.memory_key(source_text)
        and confidence >= threshold  # NaN refusé
    )


def run_engine(engine, pending: list[tuple], out: list, source: str, target: str, cfg: dict, t0: float) -> None:
    """pending : [(index, texte, vue {V}, table)]. Remplit out[index] pour chaque sortie acceptée."""
    threshold = cfg["MIN_CONFIDENCE_FROM_FF"] if source == "ff" else cfg["MIN_CONFIDENCE"]
    deadline = t0 + cfg["ENGINE_BUDGET_S"]
    todo = pending
    for strict in (False, True):  # une seconde tentative, stricte, pour les sorties refusées seulement
        failed = []
        for start in range(0, len(todo), cfg["ENGINE_BATCH"]):
            chunk = todo[start:start + cfg["ENGINE_BATCH"]]
            # ne jamais commencer un paquet sans le temps de le finir : le front coupe à 8 s
            wait = deadline - time.perf_counter() - len(chunk) * cfg["ENGINE_SEG_S"]
            if wait < 0:
                break
            try:
                results = engine.translate([c[2] for c in chunk], source, target, strict=strict, timeout=wait)
            except (EngineError, TimeoutError):
                continue  # ces segments restent incertains
            for (i, text, view, table), (raw, confidence) in zip(chunk, results):
                candidate = from_model(raw, table)
                if acceptable(text, candidate, confidence, threshold):
                    conf = round(min(max(confidence, 0.0), 1.0), 2)
                    out[i] = {"id": None, "text": candidate, "status": "machine", "confidence": conf, "origin": "llm"}
                else:
                    failed.append((i, text, view, table))
        todo = failed


def translate_segments(conn, segments: list[dict], source: str, target: str, variety: str,
                       engine=None, cfg: dict | None = None, t0: float | None = None) -> list[dict]:
    """segments : [{"id", "text", "category"}] déjà validés en forme. variety : '' si la cible n'est pas ff.
    engine : None en mode mémoire seule. Un segment en sortie par segment en entrée, même ordre."""
    out: list[dict | None] = [None] * len(segments)
    pending = []
    for i, s in enumerate(segments):
        seg_id, text = s["id"], s["text"]
        # 1. garde : un texte refusé n'est ni cherché, ni transmis, ni stocké, ni journalisé
        if not check(text):
            db.bump(conn, "unmasked_total")
            continue
        key = db.memory_key(text)
        # 2. mémoire validée par un natif
        hit = db.find_translation(conn, source, target, variety, key)
        if hit:
            _, table = canonicalize(text)
            translated = restore(hit["text"], table)
            if markers_ok(text, translated):
                out[i] = {"id": seg_id, "text": translated, "status": "validated", "confidence": 1.0, "origin": "memory"}
                continue
            db.bump(conn, "memory_bad_markers")
            log.warning("entrée de mémoire ignorée : marqueurs différents (clé %s)", hashlib.sha256(key.encode()).hexdigest()[:12])
        # 3. catégorie sensible sans mémoire : jamais de moteur (P3), liste à faire valider en priorité
        if s["category"] in SENSITIVE:
            db.note_unmatched(conn, source, target, variety, key, text)
            continue
        # 4. moteur, s'il est chargé
        if engine is None or not engine.ready():
            continue
        try:
            view, table = model_view(text)
        except ValueError:
            continue
        pending.append((i, text, view, table))

    if pending:
        run_engine(engine, pending, out, source, target, cfg, t0 if t0 is not None else time.perf_counter())
    # P5 : tout ce qui n'a pas été servi revient incertain, avec le texte source
    return [dict(o, id=s["id"]) if o else uncertain(s["id"], s["text"]) for o, s in zip(out, segments)]
