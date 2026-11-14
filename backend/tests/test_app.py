"""S1 : contrat, squelette, erreurs, CORS, health/ready/capabilities."""
import logging

import pytest

from amira import create_app
from conftest import DEV, FakeEngine
from openapi_check import assert_conforms

EXT = "chrome-extension://abcdefghijklmnop"


def test_health_conforme(client):
    r = client.get("/v1/health")
    assert r.status_code == 200 and r.get_json()["ok"] is True
    assert_conforms(r, "/v1/health")


def test_capabilities_depuis_la_configuration():
    app = create_app({**DEV, "AMIRA_TTS_ENABLED": "false", "AMIRA_LANGUAGES": "fr,ff", "AMIRA_VARIETIES": "garoua"}, engine=FakeEngine())
    r = app.test_client().get("/v1/capabilities")
    assert_conforms(r, "/v1/capabilities")
    assert r.get_json() == {"translate": True, "tts": False, "stt": False, "languages": ["fr", "ff"], "varietes": ["garoua"]}


def test_capabilities_par_defaut(client):
    body = client.get("/v1/capabilities").get_json()
    assert body["languages"] == ["fr", "en", "ff"] and body["varietes"] == ["ngaoundere", "garoua", "maroua"]
    assert body["tts"] is True and body["stt"] is False


@pytest.mark.parametrize("engine", [None, FakeEngine(loaded=False)])
def test_ready_503_avant_chargement(engine):
    r = create_app({**DEV, "AMIRA_ENGINE": "m2m100"}, engine=engine).test_client().get("/v1/ready")
    assert r.status_code == 503 and r.get_json()["error"]["code"] == "UNAVAILABLE"
    assert_conforms(r, "/v1/ready")


def test_ready_200_apres_chargement():
    engine = FakeEngine(loaded=False)
    client = create_app({**DEV, "AMIRA_ENGINE": "m2m100"}, engine=engine).test_client()
    assert client.get("/v1/ready").status_code == 503
    engine.loaded = True
    r = client.get("/v1/ready")
    assert r.status_code == 200
    assert_conforms(r, "/v1/ready")


def test_404_en_json(client):
    r = client.get("/v1/inconnu")
    assert r.status_code == 404 and r.get_json()["error"]["code"] == "BAD_REQUEST"


def test_405_en_json(client):
    r = client.post("/v1/health")
    assert r.status_code == 405 and r.get_json()["error"]["code"] == "BAD_REQUEST"


def test_413_corps_trop_gros(client):
    r = client.post("/v1/health", data=b"x" * (5 * 1024 * 1024 + 1), content_type="application/octet-stream")
    assert r.status_code == 413 and r.get_json()["error"]["code"] == "BAD_REQUEST"


def test_exception_inattendue_sans_texte(app, caplog):
    @app.get("/v1/boum")
    def boum():
        raise ValueError("CANARI-7f3a secret")

    with caplog.at_level(logging.DEBUG):
        r = app.test_client().get("/v1/boum")
    assert r.status_code == 500 and r.get_json()["error"] == {"code": "UNAVAILABLE", "message": "Service momentanément indisponible"}
    assert "CANARI-7f3a" not in r.get_data(as_text=True)
    assert "CANARI-7f3a" not in caplog.text
    assert "ValueError" in caplog.text  # le type est journalisé, pas le message


def test_preflight_cors_extension(client):
    r = client.options("/v1/translate", headers={"Origin": EXT, "Access-Control-Request-Method": "POST"})
    assert r.headers["Access-Control-Allow-Origin"] == EXT
    assert "X-Amira-Voice" in r.headers["Access-Control-Expose-Headers"]
    assert "POST" in r.headers["Access-Control-Allow-Methods"]
    assert "Content-Type" in r.headers["Access-Control-Allow-Headers"]
    assert "Access-Control-Allow-Credentials" not in r.headers


def test_cors_sur_une_erreur(client):
    r = client.get("/v1/inconnu", headers={"Origin": EXT})
    assert r.headers["Access-Control-Allow-Origin"] == EXT  # sinon le front ne peut pas lire le code d'erreur


@pytest.mark.parametrize("origin", ["https://evil.example", "http://localhost:3000", "chrome-extension-fake://x"])
def test_cors_refuse_les_sites_web(client, origin):
    r = client.get("/v1/health", headers={"Origin": origin})
    assert "Access-Control-Allow-Origin" not in r.headers


def test_cors_production_limite_a_la_liste():
    app = create_app({"AMIRA_ENV": "production", "AMIRA_ALLOWED_ORIGINS": EXT}, engine=FakeEngine())
    c = app.test_client()
    assert c.get("/v1/health", headers={"Origin": EXT}).headers["Access-Control-Allow-Origin"] == EXT
    assert "Access-Control-Allow-Origin" not in c.get("/v1/health", headers={"Origin": "chrome-extension://autre"}).headers


def test_production_sans_origines_refuse_de_demarrer():
    with pytest.raises(RuntimeError, match="AMIRA_ALLOWED_ORIGINS"):
        create_app({"AMIRA_ENV": "production"}, engine=FakeEngine())


def test_debug_coupe_hors_developpement(monkeypatch):
    monkeypatch.setenv("FLASK_DEBUG", "1")  # lu par Flask dans l'environnement du processus
    assert create_app(DEV, engine=FakeEngine()).debug is True
    assert create_app({"AMIRA_ENV": "production", "AMIRA_ALLOWED_ORIGINS": EXT}, engine=FakeEngine()).debug is False


def test_accueil_lisible_par_un_humain(client):
    r = client.get("/")
    assert r.status_code == 200 and r.mimetype == "text/html" and "extension" in r.get_data(as_text=True)


def test_guide_d_installation_servi_sans_reseau(client):
    r = client.get("/guide/")
    assert r.status_code == 200 and r.mimetype == "text/html" and "Installer Amira" in r.get_data(as_text=True)
    assert client.get("/guide").status_code == 301
    html = r.get_data(as_text=True)
    assert "http://" not in html.replace("http://127.0.0.1", "").replace("http://localhost", "").replace("http://www.w3.org", "")  # aucune ressource externe
    css = next(p for p in __import__("re").findall(r'href="\./(assets/[^"]+\.css)"', html))
    assert client.get(f"/guide/{css}").status_code == 200


def test_guide_refuse_de_sortir_de_son_dossier(client):
    for path in ("/guide/../amira/config.py", "/guide/%2e%2e/amira/config.py", "/guide/..%2f..%2f.env"):
        assert client.get(path).status_code in (301, 308, 404)
