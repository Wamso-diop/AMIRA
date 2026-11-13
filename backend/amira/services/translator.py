"""Chaîne d'un segment : garde → mémoire validée → catégorie sensible → cache machine → moteur contrôlé → incertain."""
import hashlib
import logging
import re
import threading
import time
from collections import OrderedDict

from .. import db
from ..guard import check
from ..engine import EngineError
from ..markers import canonicalize, from_model, markers_ok, model_view, restore

log = logging.getLogger("amira")

SENSITIVE = {"security_warning", "fees"}
FIRST = {"error", "instruction"}  # envoyés au moteur avant les autres (ce que l'utilisateur doit comprendre pour agir)
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


class MachineCache:
    """Sorties machine acceptées, en mémoire vive seulement : jamais sur disque, jamais dans les journaux, vidé au redémarrage.
    Clé (source, cible, clé de mémoire) ; valeur (texte masqué en numérotation canonique, confiance). LRU borné.
    Cache négatif : un texte dont la sortie a été refusée n'est pas renvoyé au moteur pendant `negative_ttl` secondes."""

    def __init__(self, size: int, negative_ttl: float):
        self.size, self.ttl = size, negative_ttl
        self._ok: OrderedDict = OrderedDict()
        self._bad: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._ok)

    def get(self, key):
        with self._lock:
            value = self._ok.get(key)
            if value is not None:
                self._ok.move_to_end(key)
            return value

    def put(self, key, value) -> None:
        with self._lock:
            self._ok[key] = value
            self._ok.move_to_end(key)
            self._bad.pop(key, None)
            while len(self._ok) > self.size:
                self._ok.popitem(last=False)

    def reject(self, key) -> None:
        with self._lock:
            self._bad[key] = time.monotonic() + self.ttl
            self._bad.move_to_end(key)
            while len(self._bad) > self.size:
                self._bad.popitem(last=False)

    def rejected(self, key) -> bool:
        with self._lock:
            until = self._bad.get(key)
            if until is not None and until <= time.monotonic():
                del self._bad[key]
                until = None
            return until is not None


def run_engine(engine, todo: list[dict], source: str, target: str, cfg: dict, t0: float) -> tuple[dict, set]:
    """todo : un représentant par texte, dans l'ordre de priorité. Renvoie ({clé: (sortie canonique, confiance)},
    {clés refusées au moins une fois et jamais acceptées})."""
    threshold = cfg["MIN_CONFIDENCE_FROM_FF"] if source == cfg["TARGET"] else cfg["MIN_CONFIDENCE"]
    deadline = t0 + cfg["ENGINE_BUDGET_S"]
    accepted, refused = {}, set()
    for strict in (False, True):  # une seconde tentative, stricte, pour les sorties refusées seulement
        failed = []
        start = 0
        while start < len(todo):
            # taille du paquet : ce que le temps restant permet, d'après la durée mesurée par le moteur ;
            # le moteur s'arrête de toute façon à l'échéance (le front coupe à 8 s)
            per_segment = engine.seconds_per_segment * (2 if strict else 1)
            fits = int((deadline - time.perf_counter()) / per_segment) if per_segment > 0 else cfg["ENGINE_BATCH"]
            chunk = todo[start:start + min(cfg["ENGINE_BATCH"], fits)]
            if not chunk:
                break
            start += len(chunk)
            try:
                results = engine.translate([p["view"] for p in chunk], source, target, strict=strict, deadline=deadline)
            except (EngineError, TimeoutError):
                continue  # ces segments restent incertains
            for p, (raw, confidence) in zip(chunk, results):
                candidate = from_model(raw, p["vtable"])
                if acceptable(p["text"], candidate, confidence, threshold):
                    canonical = restore(candidate, {o: c for c, o in p["table"].items()})
                    accepted[p["ckey"]] = (canonical, round(min(max(confidence, 0.0), 1.0), 2))
                    refused.discard(p["ckey"])
                else:
                    refused.add(p["ckey"])
                    failed.append(p)
        todo = failed
    return accepted, refused


# Fin de segment sans mot à traduire : numéros masqués, codes en capitales (« CM »), ponctuation.
TAIL_RE = re.compile(r"(?:[\s:,;!?/()#+.\-\u2013\u2014]|\{N\d+\}|\b[A-Z]{1,4}\b)+$")


def from_memory(conn, text: str, source: str, target: str, variety: str) -> str | None:
    """Traduction validée du texte entier ; sinon du début, quand la fin n'est que numéros masqués, codes et ponctuation
    (« Numéro de compte : CM {N0} ») : cette fin est recopiée telle quelle, un nombre n'est jamais traduit."""
    tail = TAIL_RE.search(text)
    tries = [(text, "")]
    if tail and tail.start() > 0 and "{N" in tail.group():
        tries.append((text[:tail.start()], tail.group()))
    for head, rest in tries:
        key = db.memory_key(head)
        hit = db.find_translation(conn, source, target, variety, key)
        if not hit:
            continue
        translated = restore(hit["text"], canonicalize(head)[1])
        translated = translated.rstrip() + rest if rest else translated
        if markers_ok(text, translated):
            return translated
        db.bump(conn, "memory_bad_markers")
        log.warning("entrée de mémoire ignorée : marqueurs différents (clé %s)", hashlib.sha256(key.encode()).hexdigest()[:12])
    return None


def machine(text: str, confidence: float) -> dict:
    return {"id": None, "text": text, "status": "machine", "confidence": confidence, "origin": "llm"}


def translate_segments(conn, segments: list[dict], source: str, target: str, variety: str,
                       engine=None, cfg: dict | None = None, t0: float | None = None, cache: MachineCache | None = None) -> list[dict]:
    """segments : [{"id", "text", "category"}] déjà validés en forme. variety : '' si la cible n'est pas ff.
    engine : None en mode mémoire seule. Un segment en sortie par segment en entrée, même ordre.
    Ordre : garde → mémoire validée → sensible (mémoire seule) → cache machine → moteur."""
    out: list[dict | None] = [None] * len(segments)
    groups: dict[tuple, list[dict]] = {}  # dédoublonnage : un texte (clé canonique) n'est traduit qu'une fois
    for i, s in enumerate(segments):
        seg_id, text = s["id"], s["text"]
        # 1. garde : un texte refusé n'est ni cherché, ni transmis, ni stocké, ni journalisé
        if not check(text):
            db.bump(conn, "unmasked_total")
            continue
        key = db.memory_key(text)
        _, table = canonicalize(text)
        # 2. mémoire validée par un natif
        translated = from_memory(conn, text, source, target, variety)
        if translated is not None:
            out[i] = {"id": seg_id, "text": translated, "status": "validated", "confidence": 1.0, "origin": "memory"}
            continue
        # 3. catégorie sensible sans mémoire : ni cache ni moteur (P3), liste à faire valider en priorité
        if s["category"] in SENSITIVE:
            db.note_unmatched(conn, source, target, variety, key, text)
            continue
        # 4. cache des sorties machine (le moteur ignore la variété)
        ckey = (source, target, key)
        cached = cache.get(ckey) if cache is not None else None
        if cached:
            translated = restore(cached[0], table)
            if markers_ok(text, translated):
                out[i] = machine(translated, cached[1])
                continue
        # 5. moteur, s'il est chargé, sauf pour un texte refusé il y a peu
        if engine is None or not engine.ready() or (cache is not None and cache.rejected(ckey)):
            continue
        try:
            view, vtable = model_view(text)
        except ValueError:
            continue
        groups.setdefault(ckey, []).append({"i": i, "text": text, "view": view, "vtable": vtable, "table": table,
                                            "ckey": ckey, "category": s["category"]})

    if groups:
        # erreurs et instructions d'abord, puis les textes courts ; l'indice départage (choix déterministe)
        todo = sorted((g[0] for g in groups.values()), key=lambda p: (p["category"] not in FIRST, len(p["text"]), p["i"]))
        accepted, refused = run_engine(engine, todo, source, target, cfg, t0 if t0 is not None else time.perf_counter())
        for ckey, (canonical, confidence) in accepted.items():
            if cache is not None:
                cache.put(ckey, (canonical, confidence))
            for p in groups[ckey]:
                translated = restore(canonical, p["table"])
                if markers_ok(p["text"], translated):
                    out[p["i"]] = machine(translated, confidence)
        if cache is not None:
            for ckey in refused:
                cache.reject(ckey)
    # P5 : tout ce qui n'a pas été servi revient incertain, avec le texte source
    return [dict(o, id=s["id"]) if o else uncertain(s["id"], s["text"]) for o, s in zip(out, segments)]
