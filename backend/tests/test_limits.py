"""S9 : limites (256 Ko JSON, débit), en-têtes, rétention (flask purge), clés d'API serveur-à-serveur."""
import pytest

from amira import create_app, db
from conftest import DEV
from openapi_check import assert_conforms

EXT = "chrome-extension://abcdefghijklmnop"


def body(n=1, text="Bonjour"):
    return {"requestId": "r", "source": "fr", "target": "ff", "variety": "ngaoundere",
            "segments": [{"id": f"s{i}", "text": text, "placeholders": []} for i in range(n)]}


@pytest.fixture
def app(db_path):
    return create_app({**DEV, "AMIRA_DB_PATH": db_path}, engine=None)


def test_json_au_dela_de_256_ko(app):
    big = {**body(), "padding": "x" * (256 * 1024)}
    r = app.test_client().post("/v1/translate", json=big)
    assert r.status_code == 413 and r.get_json()["error"]["code"] == "BAD_REQUEST"
    assert_conforms(r, "/v1/translate", "post")


def test_json_juste_sous_256_ko(app):
    r = app.test_client().post("/v1/translate", json={**body(), "padding": "x" * (250 * 1024)})
    assert r.status_code == 200


def test_debit_limite_429(db_path):
    app = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_RATE_LIMIT_PER_MIN": "3"}, engine=None)
    c = app.test_client()
    assert [c.post("/v1/translate", json=body()).status_code for _ in range(3)] == [200, 200, 200]
    r = c.post("/v1/translate", json=body())
    assert r.status_code == 429
    err = r.get_json()["error"]
    assert err["code"] == "RATE_LIMITED" and 0 < err["retryAfterMs"] <= 60_000
    assert_conforms(r, "/v1/translate", "post")
    # une autre adresse n'est pas touchée
    assert c.post("/v1/translate", json=body(), environ_base={"REMOTE_ADDR": "10.0.0.9"}).status_code == 200


def test_debit_par_defaut_large(app):
    c = app.test_client()
    assert all(c.post("/v1/translate", json=body()).status_code == 200 for _ in range(50))


def test_en_tetes_de_securite(app):
    r = app.test_client().post("/v1/translate", json=body())
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["Cache-Control"] == "no-store"


def test_purge(app, monkeypatch):
    conn = db.connect(app.config["DB_PATH"])
    old, recent = "2020-01-01T00:00:00+00:00", db.now()
    for created, status in ((old, "pending"), (old, "resolved"), (recent, "pending")):
        conn.execute("INSERT INTO feedback (segment_id, original_masked, shown, suggestion, status, created_at) "
                     "VALUES ('s', 'a', 'b', 'c', ?, ?)", (status, created))
    for key, at in (("vieux", old), ("recent", recent)):
        conn.execute("INSERT INTO unmatched VALUES ('fr', 'ff', 'ngaoundere', ?, 'x', 1, ?)", (key, at))
    conn.commit()
    result = app.test_cli_runner().invoke(args=["purge"])
    assert result.exit_code == 0, result.output
    fb = conn.execute("SELECT status, created_at FROM feedback ORDER BY id").fetchall()
    assert [tuple(r) for r in fb] == [("resolved", old), ("pending", recent)]
    assert [r[0] for r in conn.execute("SELECT key FROM unmatched")] == ["recent"]
    assert conn.execute("SELECT who, action FROM audit WHERE action = 'purge'").fetchone()[0] == "systeme"


def test_purge_duree_configurable(db_path):
    app = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_RETENTION_DAYS": "0"}, engine=None)
    conn = db.connect(db_path)
    conn.execute("INSERT INTO unmatched VALUES ('fr', 'ff', 'ngaoundere', 'k', 'x', 1, '2026-01-01T00:00:00+00:00')")
    conn.commit()
    app.test_cli_runner().invoke(args=["purge"])
    assert conn.execute("SELECT count(*) FROM unmatched").fetchone()[0] == 0


def test_cles_api_serveur(db_path):
    app = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_API_KEYS": "cle-serveur-1,cle-serveur-2"}, engine=None)
    c = app.test_client()
    r = c.post("/v1/translate", json=body())
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "BAD_REQUEST"
    assert c.post("/v1/translate", json=body(), headers={"X-Amira-Key": "cle-serveur-2"}).status_code == 200
    assert c.post("/v1/translate", json=body(), headers={"X-Amira-Key": "cle-serveur"}).status_code == 401
    assert c.post("/v1/translate", json=body(), headers={"Origin": EXT}).status_code == 200  # l'extension n'a pas de clé
    assert c.get("/v1/health").status_code == 200  # supervision


def test_sans_cles_api_tout_passe(app):
    assert app.test_client().post("/v1/translate", json=body()).status_code == 200
