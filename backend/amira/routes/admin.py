"""Outils internes des locuteurs natifs. Jamais appelés par l'extension ; jeton + réseau interne ; tout est audité."""
import csv
import hmac
import ipaddress
import os
import re
from pathlib import Path

import click
from flask import Blueprint, current_app, request
from flask.cli import with_appcontext

from .. import db
from ..errors import ApiError
from ..guard import check
from ..markers import MARKER_RE, canonicalize, markers_ok, restore
from ..services.voice import KEY_RE
from .public import MAX_CHARS, _json, get_db

admin = Blueprint("admin", __name__)

AUDIO_TYPES = {"audio/mpeg": "mp3", "audio/ogg": "ogg", "audio/webm": "webm", "audio/wav": "wav",
               "audio/x-wav": "wav", "audio/mp4": "m4a"}
GOLD_COLUMNS = ["id", "kind", "section", "page", "fr", "en", "ff", "fr_variants", "en_variants", "ff_variants",
                "notes", "observed", "n_markers"]


def refused():
    return ApiError("BAD_REQUEST", "Accès refusé", status=401)


@admin.before_request
def require_token_and_network():
    cfg = current_app.config
    try:
        addr = ipaddress.ip_address(request.remote_addr or "")
    except ValueError:
        raise refused() from None
    if not any(addr in network for network in cfg["ADMIN_NETWORKS"]):
        raise refused()
    auth = request.headers.get("Authorization", "")
    given = auth[len("Bearer "):].encode() if auth.startswith("Bearer ") else b""
    ok = False
    for token in cfg["ADMIN_TOKENS"]:  # tous comparés, en temps constant
        ok |= hmac.compare_digest(given, token.encode())
    if not given or not ok:
        raise refused()


def validator(value) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 100:
        raise ApiError("BAD_REQUEST", "validatedBy (nom du natif) obligatoire")
    return value.strip()


def language(value) -> str:
    if value not in current_app.config["LANGUAGES"]:
        raise ApiError("BAD_REQUEST", "Langue inconnue")
    return value


# --- traductions validées ---------------------------------------------------------------------

@admin.put("/translations")
def put_translation():
    cfg, req = current_app.config, _json()
    who = validator(req.get("validatedBy"))
    source, target = req.get("source"), req.get("target")
    if f"{source}>{target}" not in cfg["DIRECTIONS"]:
        raise ApiError("BAD_REQUEST", "Sens non pris en charge")
    variety = ""
    if target == "ff":
        variety = req.get("variety") or cfg["VARIETIES"][0]
        if variety not in cfg["VARIETIES"]:
            raise ApiError("BAD_REQUEST", "Variété inconnue")
    src, text = req.get("sourceMasked"), req.get("text")
    if not all(isinstance(t, str) and t.strip() and len(t) <= MAX_CHARS for t in (src, text)):
        raise ApiError("BAD_REQUEST", "sourceMasked et text attendus")
    if not (check(src) and check(text)):
        raise ApiError("BAD_REQUEST", "Texte non masqué")
    if not markers_ok(src, text):
        raise ApiError("BAD_REQUEST", "Marqueurs différents entre la source et la traduction")
    canon, table = canonicalize(src)
    text = restore(text, {o: c for c, o in table.items()})
    key = db.memory_key(src)
    conn = get_db()
    with conn:
        conn.execute(
            "INSERT INTO translations (source, target, variety, key, source_masked, text, kind, validated_by, ref, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'admin', ?) ON CONFLICT (source, target, variety, key) DO UPDATE SET "
            "source_masked = excluded.source_masked, text = excluded.text, kind = excluded.kind, "
            "validated_by = excluded.validated_by, ref = 'admin', updated_at = excluded.updated_at",
            (source, target, variety, key, canon, text, req.get("kind") if req.get("kind") in ("ui", "message", "glossaire") else None,
             who, db.now()),
        )
        conn.execute("DELETE FROM unmatched WHERE source = ? AND target = ? AND variety = ? AND key = ?", (source, target, variety, key))
        db.audit(conn, who, "put_translation", f"{source}>{target}:{variety}:{key}")
    return "", 204


@admin.get("/unmatched")
def unmatched():
    rows = get_db().execute("SELECT source, target, variety, text_masked, requests, last_at FROM unmatched "
                            "ORDER BY requests DESC, last_at DESC LIMIT 500").fetchall()
    return {"items": [{"source": r["source"], "target": r["target"], "variety": r["variety"], "textMasked": r["text_masked"],
                       "requests": r["requests"], "lastAt": r["last_at"]} for r in rows]}


# --- signalements -----------------------------------------------------------------------------

@admin.get("/feedback")
def list_feedback():
    rows = get_db().execute("SELECT id, segment_id, original_masked, shown, suggestion, status, created_at FROM feedback "
                            "WHERE status = ? ORDER BY id LIMIT 500", (request.args.get("status", "pending"),)).fetchall()
    return {"items": [{"id": r["id"], "segmentId": r["segment_id"], "originalMasked": r["original_masked"], "shown": r["shown"],
                       "suggestion": r["suggestion"], "status": r["status"], "createdAt": r["created_at"]} for r in rows]}


@admin.post("/feedback/<int:fid>/resolve")
def resolve_feedback(fid: int):
    who = validator(_json().get("validatedBy"))
    conn = get_db()
    with conn:
        cur = conn.execute("UPDATE feedback SET status = 'resolved' WHERE id = ? AND status = 'pending'", (fid,))
        if cur.rowcount == 0:
            raise ApiError("BAD_REQUEST", "Signalement inconnu", status=404)
        db.audit(conn, who, "resolve_feedback", str(fid))
    return "", 204


# --- enregistrements ----------------------------------------------------------------------------

@admin.get("/recordings/missing")
def missing_recordings():
    rows = get_db().execute("SELECT segment_key, text, requests, last_at FROM missing_audio WHERE language = ? "
                            "ORDER BY requests DESC, last_at DESC LIMIT 500", (language(request.args.get("language")),)).fetchall()
    return {"items": [{"segmentKey": r["segment_key"], "text": r["text"], "requests": r["requests"], "lastAt": r["last_at"]}
                      for r in rows]}


def recording_target(key: str) -> tuple[str, str]:
    if not KEY_RE.fullmatch(key):  # le nom du fichier vient de la clé : aucune traversée possible
        raise ApiError("BAD_REQUEST", "segmentKey invalide")
    return key, language(request.args.get("language"))


@admin.put("/recordings/<key>")
def put_recording(key: str):
    key, lang = recording_target(key)
    who = validator(request.args.get("validatedBy"))
    ext = AUDIO_TYPES.get(request.mimetype)
    if not ext:
        raise ApiError("BAD_REQUEST", "Type audio non autorisé")
    data = request.get_data()
    if not data:
        raise ApiError("BAD_REQUEST", "Audio vide")
    folder = Path(current_app.config["RECORDINGS_DIR"])
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{key}.{lang}.{ext}"
    tmp = path.with_suffix(".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    conn = get_db()
    with conn:
        old = conn.execute("SELECT path FROM recordings WHERE segment_key = ? AND language = ?", (key, lang)).fetchone()
        if old and Path(old["path"]) != path:
            Path(old["path"]).unlink(missing_ok=True)
        conn.execute(
            "INSERT INTO recordings (segment_key, language, path, mime, speaker, created_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (segment_key, language) DO UPDATE SET path = excluded.path, mime = excluded.mime, "
            "speaker = excluded.speaker, created_at = excluded.created_at",
            (key, lang, str(path), request.mimetype, who, db.now()),
        )
        conn.execute("DELETE FROM missing_audio WHERE segment_key = ? AND language = ?", (key, lang))
        db.audit(conn, who, "put_recording", f"{key}:{lang}")
    return "", 204


@admin.delete("/recordings/<key>")
def delete_recording(key: str):
    key, lang = recording_target(key)
    who = validator(request.args.get("validatedBy"))
    conn = get_db()
    with conn:
        row = conn.execute("SELECT path FROM recordings WHERE segment_key = ? AND language = ?", (key, lang)).fetchone()
        if not row:
            raise ApiError("BAD_REQUEST", "Enregistrement inconnu", status=404)
        Path(row["path"]).unlink(missing_ok=True)
        conn.execute("DELETE FROM recordings WHERE segment_key = ? AND language = ?", (key, lang))
        db.audit(conn, who, "delete_recording", f"{key}:{lang}")
    return "", 204


# --- export des entrées admin au format du CSV gold -----------------------------------------------

def to_gold(text: str) -> str:
    """{N0} → {V1}, {N1} → {V2}… (format du gold). {B}/{E} restent tels quels."""
    return re.sub(r"\{N(\d+)\}", lambda m: f"{{V{int(m.group(1)) + 1}}}", text)


@click.command("export-admin")
@click.argument("path")
@with_appcontext
def export_admin(path: str):
    """Écrit les traductions validées depuis l'admin au format de data/gold_fulfulde.csv (à relire puis fusionner)."""
    conn = db.connect(current_app.config["DB_PATH"])
    rows = conn.execute("SELECT source, target, variety, source_masked, text, kind, validated_by, updated_at "
                        "FROM translations WHERE ref = 'admin' ORDER BY updated_at, source, target").fetchall()
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=GOLD_COLUMNS)
        w.writeheader()
        for i, r in enumerate(rows, 1):
            line = dict.fromkeys(GOLD_COLUMNS, "")
            line.update({"id": f"admin-{i:04d}", "kind": r["kind"] or "", r["source"]: to_gold(r["source_masked"]),
                         r["target"]: to_gold(r["text"]), "n_markers": str(len(MARKER_RE.findall(r["source_masked"]))),
                         "notes": f"{r['source']}>{r['target']} {r['variety'] or '-'} {r['validated_by']} {r['updated_at']}"})
            w.writerow(line)
    click.echo(f"{len(rows)} entrées admin écrites dans {path}")
