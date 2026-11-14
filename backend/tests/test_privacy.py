"""S9 : aucun texte (même masqué) dans les journaux ; canari refusé absent de partout."""
import logging
import re
import sqlite3

import pytest

from amira import create_app
from amira.engine import FakeEngine
from conftest import DEV

CANARI = "CANARI-9e2f jean.canari@exemple.cm +237 699 12 34 56"
MASKED = "Texte masqué CANARIMASQUE {N0}"  # passe la garde : ne doit pas non plus être journalisé


@pytest.fixture
def setup(db_path, tmp_path):
    engine = FakeEngine()
    app = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ENGINE": "m2m100", "AMIRA_RECORDINGS_DIR": str(tmp_path / "rec")},
                     engine=engine)
    return app, engine, db_path


def everything(app):
    c = app.test_client()
    segs = [{"id": "a", "text": CANARI, "placeholders": []},
            {"id": "b", "text": CANARI, "placeholders": [], "categoryHint": "security_warning"},
            {"id": "c", "text": MASKED, "placeholders": ["{N0}"]},
            {"id": "d", "text": MASKED + " alerte", "placeholders": ["{N0}"], "categoryHint": "fees"}]
    c.post("/v1/translate", json={"requestId": "abc123", "source": "fr", "target": "ff", "variety": "ngaoundere", "segments": segs})
    c.post("/v1/tts", json={"text": CANARI, "language": "ff", "segmentKey": "k12345678"})
    c.post("/v1/tts", json={"text": MASKED, "language": "ff", "segmentKey": "k12345678"})
    c.post("/v1/feedback", json={"segmentId": "a", "originalMasked": CANARI, "shown": "x", "suggestion": "y"})
    c.post("/v1/feedback", json={"segmentId": "a", "originalMasked": MASKED, "shown": MASKED, "suggestion": MASKED})
    c.post("/v1/translate", data="{" + CANARI, content_type="application/json")  # corps illisible


def dump_db(path):
    conn = sqlite3.connect(path)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    return " ".join(str(row) for t in tables for row in conn.execute(f"SELECT * FROM {t}"))


def test_canari_absent_des_journaux(setup, caplog):
    app, _, _ = setup
    with caplog.at_level(logging.DEBUG):
        everything(app)
    assert "CANARI" not in caplog.text and "699" not in caplog.text and "@exemple" not in caplog.text


def test_canari_refuse_absent_de_la_base(setup):
    app, _, path = setup
    everything(app)
    db = dump_db(path)
    assert "CANARI-9e2f" not in db and "699 12" not in db and "jean.canari" not in db
    assert "CANARIMASQUE" in db  # le texte masqué, lui, peut être stocké (unmatched, feedback, missing_audio)


def test_canari_refuse_jamais_au_moteur(setup):
    app, engine, _ = setup
    everything(app)
    sent = " ".join(t for call in engine.calls for t in call[0])
    assert "CANARI-9e2f" not in sent and "CANARIMASQUE" in sent


def test_une_ligne_par_requete_sans_texte(setup, caplog):
    app, _, _ = setup
    with caplog.at_level(logging.INFO, logger="amira"):
        app.test_client().post("/v1/translate", json={"requestId": "abc123", "source": "fr", "target": "ff", "variety": "ngaoundere",
                                                      "segments": [{"id": "a", "text": MASKED, "placeholders": []},
                                                                   {"id": "b", "text": CANARI, "placeholders": []}]})
    lines = [r.getMessage() for r in caplog.records if r.name == "amira" and r.getMessage().startswith("POST")]
    assert len(lines) == 1
    line = lines[0]
    assert re.fullmatch(r"POST /v1/translate 200 \d+ms rid=abc123 n=2 memory=0 machine=1 uncertain=1 refused=1", line), line


@pytest.mark.parametrize("rid,expected", [("abc-123_DEF", "abc-123_DEF"), ("a\nFAUX 500", "-"), ("x" * 65, "-"),
                                          (CANARI, "-"), (5, "-")])
def test_request_id_assaini(setup, caplog, rid, expected):
    app, _, _ = setup
    with caplog.at_level(logging.INFO, logger="amira"):
        app.test_client().post("/v1/translate", json={"requestId": rid, "source": "fr", "target": "ff", "variety": "ngaoundere",
                                                      "segments": [{"id": "a", "text": "Bonjour", "placeholders": []}]})
    (line,) = [r.getMessage() for r in caplog.records if r.getMessage().startswith("POST")]
    assert f" rid={expected} " in line and "\n" not in line


def test_journal_d_une_erreur(setup, caplog):
    app, _, _ = setup
    with caplog.at_level(logging.INFO, logger="amira"):
        app.test_client().get("/v1/inconnu?q=" + "CANARI")
    (line,) = [r.getMessage() for r in caplog.records if r.getMessage().startswith("GET")]
    assert line.startswith("GET /v1/inconnu 404 ") and "CANARI" not in line  # chemin sans la query string
