"""S8 : /v1/feedback → file « pending » après la garde ; jamais d'entrée validated."""
import pytest

from amira import create_app, db
from conftest import DEV
from openapi_check import assert_conforms

OK = {"segmentId": "s12", "originalMasked": "Frais de dossier : {N0}", "shown": "<<Frais de dossier : {N0}>>", "suggestion": "Frais à payer : {N0}"}


@pytest.fixture
def fb_app(db_path):
    return create_app({**DEV, "AMIRA_DB_PATH": db_path}, engine=None)


def post(app, body):
    r = app.test_client().post("/v1/feedback", json=body)
    assert_conforms(r, "/v1/feedback", "post")
    return r


def test_feedback_en_attente(fb_app):
    conn = db.connect(fb_app.config["DB_PATH"])
    before = conn.execute("SELECT count(*) FROM translations").fetchone()[0]
    r = post(fb_app, OK)
    assert r.status_code == 204 and r.data == b""
    rows = conn.execute("SELECT segment_id, original_masked, shown, suggestion, status FROM feedback").fetchall()
    assert [tuple(r) for r in rows] == [("s12", OK["originalMasked"], OK["shown"], OK["suggestion"], "pending")]
    assert conn.execute("SELECT count(*) FROM translations").fetchone()[0] == before  # jamais validated


def test_feedback_ne_rend_pas_validated(fb_app):
    post(fb_app, OK)
    r = fb_app.test_client().post("/v1/translate", json={"requestId": "r", "source": "fr", "target": "ff", "variety": "ngaoundere",
                                                         "segments": [{"id": "a", "text": OK["originalMasked"], "placeholders": []}]})
    assert r.get_json()["segments"][0]["status"] == "uncertain"


@pytest.mark.parametrize("field", ["originalMasked", "shown", "suggestion"])
def test_champ_refuse_par_la_garde(fb_app, field):
    r = post(fb_app, dict(OK, **{field: "CANARI-fb jean@exemple.cm"}))
    assert r.status_code == 204
    conn = db.connect(fb_app.config["DB_PATH"])
    assert conn.execute("SELECT count(*) FROM feedback").fetchone()[0] == 0
    assert db.counter(conn, "unmasked_total") == 1


@pytest.mark.parametrize("body", [
    {k: v for k, v in OK.items() if k != "suggestion"},
    dict(OK, shown=None),
    dict(OK, suggestion="x" * 1001),
    dict(OK, segmentId="CANARI jean@exemple.cm"),  # un identifiant, pas un texte
    dict(OK, segmentId=""),
    ["pas", "un", "objet"],
])
def test_feedback_invalide(fb_app, body):
    r = post(fb_app, body)
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "BAD_REQUEST"
