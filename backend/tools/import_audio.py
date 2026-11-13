"""Charge les audios du natif, rangés par tools.organize_audio, dans la table recordings. Rejouable.

Usage (depuis backend/) : python -m tools.import_audio data/audio data/gold_fulfulde.csv --validator natif-1
Seuls les fichiers reliés à une ligne gold sont chargés (ni a_verifier/, ni hors-gold). Une phrase enregistrée en
deux morceaux est recollée (p1 + p2, ffmpeg). L'audio fulfulde est rangé sous la clé de chaque source fr/en de la
ligne (variantes comprises), comme le panneau la calcule : /v1/tts le sert alors tel quel.
Un enregistrement déposé par l'admin n'est jamais remplacé.
"""
import argparse
import csv
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from amira import db
from amira.services.voice import segment_key
from tools.import_gold import refusal, to_front, variants

SUFFIX = ".gold.m4a"  # distingue nos fichiers de ceux de l'admin (<clé>.<langue>.<ext>)
LANG = "ff"


def concat(parts: list[Path], dest: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        listing = Path(tmp) / "list.txt"
        listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", str(dest)], check=True)


def import_audio(conn, audio_dir: Path, gold: Path, rec_dir: Path, validator: str) -> dict:
    if not validator.strip():
        raise ValueError("nom du natif obligatoire (--validator)")
    with gold.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    with (audio_dir / "index.csv").open(encoding="utf-8", newline="") as f:
        # première prise d'abord : l'index est trié par nom, « _prise2 » vient après
        index = sorted(csv.DictReader(f), key=lambda x: ("_prise" in x["fichier"], x["fichier"]))

    def file_for(gid: str, part: str) -> Path | None:
        hit = next((x for x in index if x["partie"] == part and gid in x["ids"].split("|")), None)
        return audio_dir / hit["fichier"] if hit else None

    rec_dir.mkdir(parents=True, exist_ok=True)
    admin = {r["segment_key"] for r in conn.execute(
        "SELECT segment_key, path FROM recordings WHERE language = ?", (LANG,)).fetchall() if not r["path"].endswith(SUFFIX)}
    imported, incomplete, wanted = [], [], {}
    for row in rows:
        if refusal(row) or row["id"] in imported:
            continue
        whole = file_for(row["id"], "entier")
        p1, p2 = file_for(row["id"], "p1"), file_for(row["id"], "p2")
        if not whole and not (p1 and p2):
            if p1 or p2:
                incomplete.append(row["id"])
            continue
        keys = {segment_key(to_front(t)) for c in ("fr", "en") for t in [row[c], *variants(row[f"{c}_variants"])] if t.strip()}
        for k in sorted(keys - admin - set(wanted)):
            dest = rec_dir / f"{k}.{LANG}{SUFFIX}"
            if whole:
                shutil.copyfile(whole, dest)
            else:
                concat([p1, p2], dest)
            wanted[k] = dest
        imported.append(row["id"])

    stamp = db.now()
    with conn:
        for k, dest in wanted.items():
            conn.execute(
                "INSERT INTO recordings (segment_key, language, path, mime, speaker, created_at) VALUES (?, ?, ?, 'audio/mp4', ?, ?) "
                "ON CONFLICT (segment_key, language) DO UPDATE SET path = excluded.path, mime = excluded.mime, "
                "speaker = excluded.speaker, created_at = excluded.created_at",
                (k, LANG, str(dest), validator, stamp),
            )
            conn.execute("DELETE FROM missing_audio WHERE segment_key = ? AND language = ?", (k, LANG))
        # nos fichiers disparus de l'index (ligne gold retirée, fichier déplacé) : on les retire aussi
        for r in conn.execute("SELECT segment_key, path FROM recordings WHERE language = ?", (LANG,)).fetchall():
            if r["path"].endswith(SUFFIX) and r["segment_key"] not in wanted:
                Path(r["path"]).unlink(missing_ok=True)
                conn.execute("DELETE FROM recordings WHERE segment_key = ? AND language = ?", (r["segment_key"], LANG))
        db.audit(conn, validator, "import_audio", f"{len(wanted)} enregistrements")
    return {"imported": imported, "keys": len(wanted), "incomplete": incomplete}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("audio", type=Path)
    ap.add_argument("gold", type=Path)
    ap.add_argument("--validator", required=True, help="nom du locuteur natif qui a enregistré")
    ap.add_argument("--db", default=os.environ.get("AMIRA_DB_PATH", "data/amira.sqlite3"))
    ap.add_argument("--recordings", type=Path, default=Path(os.environ.get("AMIRA_RECORDINGS_DIR", "media/recordings")))
    args = ap.parse_args()
    report = import_audio(db.connect(args.db), args.audio, args.gold, args.recordings, args.validator)
    print(f"lignes gold avec audio : {len(report['imported'])}, clés chargées : {report['keys']}")
    print(f"phrases incomplètes (un morceau manque) : {' '.join(report['incomplete']) or 'aucune'}")


if __name__ == "__main__":
    main()
