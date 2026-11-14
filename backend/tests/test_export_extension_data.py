"""Export de la mémoire et des voix vers l'extension : même clés que le serveur, budget respecté, vecteurs fidèles au serveur."""
import csv
import hashlib

import pytest

from amira import config, db
from amira.services.translator import from_memory
from amira.services.voice import audio_key
from tools import export_extension_data as ex
from tools import new_language
from tools.import_gold import import_gold


@pytest.fixture
def mini(tmp_path, monkeypatch):
    """Langue « zz » à trois lignes (mot de la langue = valeur de test sans sens), dans un dossier temporaire."""
    new_language.create("zz", ["nord"], tmp_path)
    monkeypatch.setattr(config, "LANGUAGES_DIR", tmp_path)
    gold = tmp_path / "zz" / "gold.csv"
    head = gold.read_text(encoding="utf-8").strip().split(",")
    lines = []
    for i, (kind, fr, en, zz) in enumerate([("message", "Erreur survenue.", "An error occurred.", "Mot-a"),
                                           ("ui", "Votre compte", "Your account", "Mot-b"),
                                           ("glossaire", "Solde", "Balance", "Mot-c")], 1):
        row = dict.fromkeys(head, "")
        row.update(id=f"g{i}", kind=kind, fr=fr, en=en, zz=zz)
        lines.append(row)
    with gold.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=head)
        w.writeheader()
        w.writerows(lines)
    conn = db.connect(str(tmp_path / "t.sqlite3"))
    import_gold(conn, gold, "natif-1", "zz", "nord")
    return conn, lines, tmp_path


def test_la_memoire_exportee_a_les_cles_du_serveur(mini):
    conn, rows, _ = mini
    tables = ex.export_memory(conn)
    assert set(tables) == {"fr>zz|nord", "en>zz|nord", "zz>fr|", "zz>en|"}
    key = db.memory_key("Erreur survenue.")
    assert tables["fr>zz|nord"][key] == "Mot-a"
    assert from_memory(conn, "Erreur survenue.", "fr", "zz", "nord") == tables["fr>zz|nord"][key]


def enregistrements(conn, tmp_path, textes):
    """Une voix par texte : tailles 40, 30, 30 octets ; la dernière est la copie exacte de la deuxième (dédoublonnage)."""
    for text, data in textes:
        path = tmp_path / f"{hashlib.sha256(text.encode()).hexdigest()[:6]}.m4a"
        path.write_bytes(data)
        conn.execute("INSERT INTO recordings (segment_key, language, path, mime, speaker, created_at) VALUES (?, 'zz', ?, 'audio/mp4', 'n', 'x')",
                     (audio_key(text), str(path)))
    conn.commit()


def test_les_voix_respectent_le_budget_et_la_priorite(mini):
    conn, rows, tmp = mini
    enregistrements(conn, tmp, [("Erreur survenue.", b"a" * 40), ("Votre compte", b"b" * 30), ("Solde", b"c" * 30)])
    index, bilan = ex.export_audio(conn, rows, "zz", tmp / "out", budget=75)
    # le message d'abord (40), puis le libellé (30) : 70 octets ; le mot (30) ne tient plus dans les 75
    assert audio_key("Erreur survenue.") in index and audio_key("Votre compte") in index and audio_key("Solde") not in index
    assert bilan["bytes"] == 70 and bilan["files"] == 2
    assert {p.name for p in (tmp / "out").glob("*.m4a")} == set(index.values())


def test_deux_cles_avec_le_meme_audio_ne_comptent_qu_une_fois(mini):
    conn, rows, tmp = mini
    enregistrements(conn, tmp, [("Erreur survenue.", b"x" * 50), ("Your account", b"x" * 50)])  # même contenu, clés différentes
    index, bilan = ex.export_audio(conn, rows, "zz", tmp / "out", budget=60)
    assert bilan["files"] == 1 and bilan["bytes"] == 50
    assert index[audio_key("Erreur survenue.")] == index[audio_key("Your account")]


def test_les_vecteurs_sont_ceux_du_vrai_serveur(mini):
    conn, rows, _ = mini
    vec = ex.vectors(conn, rows, "zz", "nord")
    exact = next(v for v in vec if v["text"] == "Erreur survenue." and v["source"] == "fr" and v["target"] == "zz")
    assert exact["expected"] == "Mot-a"
    assert any(v["expected"] is None for v in vec)  # texte inconnu, sens interdit fr>en
    assert all(v["expected"] == from_memory(conn, v["text"], v["source"], v["target"], v["variety"]) for v in vec)
