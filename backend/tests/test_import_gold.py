"""S4 : base SQLite et import idempotent du CSV gold."""
import csv
import sqlite3

import pytest

from amira import db
from gold import GOLD, rows, to_front
from tools.import_gold import import_gold

V = "natif-1"


@pytest.fixture
def conn(tmp_path):
    return db.connect(str(tmp_path / "t.sqlite3"))


def dump(conn):
    return conn.execute("SELECT source, target, variety, key, source_masked, text, kind, validated_by, ref, updated_at "
                        "FROM translations ORDER BY 1, 2, 3, 4").fetchall()


def write_csv(path, data):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
        w.writeheader()
        w.writerows(data)
    return path


def test_schema_sept_tables(conn):
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"translations", "feedback", "unmatched", "recordings", "missing_audio", "audit", "counters"} <= names


def test_import_de_toutes_les_lignes(conn):
    report = import_gold(conn, GOLD, V)
    # seuls les nombres écrits en lettres sont écartés : un nombre ne se traduit jamais
    assert report["rows"] == len(rows()) and {r["reason"] for r in report["refused"]} == {"nombre"}
    imported = len(rows()) - len(report["refused"])
    assert report["entries"] > imported * 2  # au moins fr>ff et ff>fr par ligne, plus en et variantes
    assert len(dump(conn)) == report["entries"]
    assert {r[7] for r in dump(conn)} == {V}


def test_deux_imports_donnent_la_meme_base(conn, monkeypatch):
    monkeypatch.setattr(db, "now", lambda: "2026-01-01T00:00:00+00:00")
    import_gold(conn, GOLD, V)
    first = dump(conn)
    monkeypatch.setattr(db, "now", lambda: "2026-02-02T00:00:00+00:00")
    import_gold(conn, GOLD, V)
    assert dump(conn) == first  # updated_at compris : rien n'a changé


def test_conversion_des_marqueurs(conn):
    import_gold(conn, GOLD, V)
    row = next(r for r in rows() if r["n_markers"] == "1")
    hit = db.find_translation(conn, "fr", "ff", "ngaoundere", db.memory_key(to_front(row["fr"])))
    assert hit is not None and hit["text"] == to_front(row["ff"]) and "{N0}" in hit["text"]
    assert not any("{V" in r[4] + r[5] for r in dump(conn))


def test_sens_inverse_et_variete(conn):
    import_gold(conn, GOLD, V)
    row = rows()[5]
    key = db.memory_key(to_front(row["ff"]))
    assert db.find_translation(conn, "ff", "fr", "", key)["text"] == row["fr"]
    assert db.find_translation(conn, "ff", "en", "", key)["text"] == row["en"]
    # la variété ne compte que vers ff
    fr_key = db.memory_key(row["fr"])
    assert db.find_translation(conn, "fr", "ff", "ngaoundere", fr_key)["text"] == row["ff"]
    assert db.find_translation(conn, "fr", "ff", "garoua", fr_key) is None


def test_variantes(conn):
    import_gold(conn, GOLD, V)
    row = next(r for r in rows() if r["fr_variants"])
    assert db.find_translation(conn, "fr", "ff", "ngaoundere", db.memory_key(row["fr_variants"]))["text"] == row["ff"]
    row = next(r for r in rows() if r["ff_variants"])
    assert db.find_translation(conn, "ff", "fr", "", db.memory_key(row["ff_variants"]))["text"] == row["fr"]


def test_conflit_signale_ui_avant_glossaire(conn):
    report = import_gold(conn, GOLD, V)
    by_id = {r["id"]: r for r in rows()}
    assert {"direction": "ff>fr", "kept": "g0028", "dropped": "g0002"} in report["conflicts"]
    assert {"direction": "ff>en", "kept": "g0028", "dropped": "g0002"} in report["conflicts"]
    key = db.memory_key(by_id["g0028"]["ff"])
    assert db.find_translation(conn, "ff", "fr", "", key)["text"] == by_id["g0028"]["fr"]


def test_cle_normalisee():
    assert db.memory_key("  Votre  SOLDE est de {B0}{N0}{/B0}. ") == "votre solde est de {B0}{N0}{/B0}"
    assert db.memory_key("Payer {N3} et {N1} !") == "payer {N0} et {N1}"  # renumérotation canonique
    assert db.memory_key("Valider…") == db.memory_key("valider")


def test_numerotation_canonique(conn, tmp_path):
    # source « {V2} … {V1} » : la clé renumérote, la traduction suit (textes neutres, pas de fulfulde)
    row = dict(rows()[0], id="x9", fr="De {V2} vers {V1}", en="From {V2} to {V1}", ff="a {V1} b {V2}", n_markers="2",
               fr_variants="", en_variants="", ff_variants="")
    import_gold(conn, write_csv(tmp_path / "g.csv", [row]), V)
    hit = db.find_translation(conn, "fr", "ff", "ngaoundere", db.memory_key("De {N1} vers {N0}"))
    assert (hit["source_masked"], hit["text"]) == ("De {N0} vers {N1}", "a {N1} b {N0}")


def test_lignes_invalides_refusees(conn, tmp_path):
    data = rows()[:3]
    bad_markers = dict(data[0], id="x1", fr="Payer {V1}", en="Pay {V1}", ff=to_front(data[0]["ff"]), n_markers="1")
    bad_count = dict(data[1], id="x2", n_markers="2")
    bad_guard = dict(data[2], id="x3", fr="Payer 5000 FCFA")
    report = import_gold(conn, write_csv(tmp_path / "g.csv", [bad_markers, bad_count, bad_guard] + rows()[3:6]), V)
    assert [r["id"] for r in report["refused"]] == ["x1", "x2", "x3"]
    assert {r["reason"] for r in report["refused"]} == {"marqueurs", "n_markers", "garde"}
    assert report["rows"] == 6
    assert not any("5000" in r[4] for r in dump(conn))


def test_ligne_retiree_du_csv_disparait(conn, tmp_path):
    import_gold(conn, GOLD, V)
    data = rows()
    data[5] = dict(data[5], fr=data[5]["fr"] + " corrigé")
    import_gold(conn, write_csv(tmp_path / "g.csv", data), V)
    assert db.find_translation(conn, "fr", "ff", "ngaoundere", db.memory_key(rows()[5]["fr"])) is None
    assert db.find_translation(conn, "fr", "ff", "ngaoundere", db.memory_key(data[5]["fr"]))["text"] == data[5]["ff"]


def test_ne_modifie_jamais_le_csv(conn):
    before = GOLD.read_bytes()
    import_gold(conn, GOLD, V)
    assert GOLD.read_bytes() == before


def test_audit_de_l_import(conn):
    import_gold(conn, GOLD, V)
    (who, action), = conn.execute("SELECT who, action FROM audit").fetchall()
    assert (who, action) == (V, "import_gold")


def test_validateur_obligatoire(conn):
    with pytest.raises(ValueError):
        import_gold(conn, GOLD, "  ")


def test_requetes_parametrees(conn):
    # une clé hostile est une valeur, jamais du SQL
    assert db.find_translation(conn, "fr", "ff", "ngaoundere", "x' OR '1'='1") is None
    assert conn.execute("SELECT count(*) FROM sqlite_master").fetchone()[0] > 0


def test_compteur(conn):
    db.bump(conn, "unmasked_total")
    db.bump(conn, "unmasked_total")
    assert db.counter(conn, "unmasked_total") == 2
    assert db.counter(conn, "inconnu") == 0


def test_la_base_cree_son_dossier(tmp_path):
    """Dans un clone neuf, data/ n'existe pas : la première connexion le crée."""
    path = tmp_path / "absent" / "sous" / "amira.sqlite3"
    db.connect(str(path)).close()
    assert path.exists()
