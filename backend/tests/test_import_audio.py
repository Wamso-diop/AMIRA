"""Chargement des audios du natif (rangés par tools.organize_audio) dans la table recordings (textes factices)."""
import csv
import subprocess
from pathlib import Path

import pytest

from amira import db
from amira.services.voice import audio_key, find_recording
from tools.import_audio import import_audio
from tools.import_gold import to_front
from tools.organize_audio import organize

HEAD = ["id", "kind", "section", "page", "fr", "en", "ff", "fr_variants", "en_variants", "ff_variants", "notes",
        "observed", "n_markers"]
GOLD = [  # id, kind, fr, en, ff, fr_variants
    ("g1", "ui", "Bonjour", "Hello", "alfa beta", "Salut"),
    ("g2", "message", "Montant : {V1}. Confirmez.", "Amount: {V1}. Confirm.", "Gamma {V1}. Delta zeta.", ""),
    ("g3", "message", "Code faux. Rappelez.", "Wrong code. Call back.", "Kappa mu. Delta zeta.", ""),
    ("g4", "message", "Solde bas.", "Low balance.", "Omega psi. Rho tau.", ""),
    ("g5", "glossaire", "deux", "two", "zwa", ""),
]
# (nom du fichier du natif, durée en secondes)
AUDIO = [("alfa beta.m4a", 1), ("alfa beta-1.m4a", 3), ("Gamma {} FCFA.m4a", 1), ("Kappa mu.m4a", 1),
         ("Delta zeta.m4a", 2), ("Omega psi.m4a", 1), ("zwa.m4a", 1), ("Rien du tout.m4a", 1)]


def tone(path: Path, seconds: int):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                    "-c:a", "aac", str(path)], check=True)


def duration(path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True)
    return float(out.stdout)


@pytest.fixture
def setup(tmp_path):
    gold = tmp_path / "gold.csv"
    with gold.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEAD)
        for i, kind, fr, en, ff, frv in GOLD:
            w.writerow([i, kind, "", "1", fr, en, ff, frv, "", "", "", "oui", fr.count("{V")])
    src = tmp_path / "src"
    src.mkdir()
    for name, s in AUDIO:
        tone(src / name, s)
    organize(src, gold, tmp_path / "audio")
    conn = db.connect(str(tmp_path / "t.sqlite3"))
    return conn, gold, tmp_path / "audio", tmp_path / "rec"


def key(text):
    return audio_key(to_front(text))


def test_phrase_entiere_pour_chaque_source(setup):
    conn, gold, audio, rec = setup
    report = import_audio(conn, audio, gold, rec, "natif-1")
    for fr in ("Bonjour", "Salut", "Hello"):  # fr, variante fr, en : la même voix fulfulde
        row = find_recording(conn, key(fr), "ff")
        assert row and row["mime"] == "audio/mp4" and round(duration(row["path"])) == 1  # première prise
    assert "g1" in report["imported"]


def test_phrase_coupee_recollee(setup):
    conn, gold, audio, rec = setup
    report = import_audio(conn, audio, gold, rec, "natif-1")
    # g2 = début propre + fin commune avec g3 ; g3 = la même chose
    for text, part1 in (("Montant : {V1}. Confirmez.", 1), ("Code faux. Rappelez.", 1)):
        row = find_recording(conn, key(text), "ff")
        assert row and round(duration(row["path"])) == part1 + 2
    assert {"g2", "g3"} <= set(report["imported"])
    # g4 : il manque la fin, rien n'est chargé ; g5 : nombre (jamais traduit) ; fichier hors gold ignoré
    assert find_recording(conn, key("Solde bas."), "ff") is None and report["incomplete"] == ["g4"]
    assert find_recording(conn, key("deux"), "ff") is None and "g5" not in report["imported"]


def test_rejouable_sans_toucher_aux_enregistrements_de_l_admin(setup):
    conn, gold, audio, rec = setup
    rec.mkdir()
    admin = rec / f"{key('Hello')}.ff.m4a"
    admin.write_bytes(b"admin")
    conn.execute("INSERT INTO recordings VALUES (?, 'ff', ?, 'audio/mp4', 'natif-2', '2026-01-01')", (key("Hello"), str(admin)))
    conn.commit()
    first = import_audio(conn, audio, gold, rec, "natif-1")
    again = import_audio(conn, audio, gold, rec, "natif-1")
    assert first == again
    assert find_recording(conn, key("Hello"), "ff")["path"] == str(admin) and admin.read_bytes() == b"admin"
    assert conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0] == 7  # g1×3, g2×2, g3×2
