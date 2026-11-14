"""S9 : P6, aucun appel sortant pendant translate, tts et feedback (sockets interdits)."""
import socket

import pytest

from amira import create_app
from amira.engine import FakeEngine
from conftest import DEV


@pytest.fixture
def no_network(monkeypatch):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append(args)
        raise OSError("réseau interdit pendant le test")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    return attempts


def test_le_blocage_fonctionne(no_network):
    with pytest.raises(OSError):
        socket.create_connection(("example.com", 443))


def test_translate_tts_feedback_sans_reseau(db_path, tmp_path, no_network):
    app = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ENGINE": "m2m100", "AMIRA_RECORDINGS_DIR": str(tmp_path)},
                     engine=FakeEngine())
    c = app.test_client()
    r = c.post("/v1/translate", json={"requestId": "r", "source": "fr", "target": "ff", "variety": "ngaoundere",
                                      "segments": [{"id": "a", "text": "Texte inconnu", "placeholders": []}]})
    assert r.status_code == 200 and r.get_json()["segments"][0]["status"] == "machine"
    assert c.post("/v1/tts", json={"text": "Bonjour", "language": "ff", "segmentKey": "k12345678"}).status_code == 204
    assert c.post("/v1/feedback", json={"segmentId": "a", "originalMasked": "x", "shown": "y", "suggestion": "z"}).status_code == 204
    assert no_network == []


@pytest.mark.model
def test_vrai_modele_sans_reseau(db_path, no_network):

    from real_engine import real_engine

    engine = real_engine()
    engine.load()
    app = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ENGINE": "m2m100"}, engine=engine)
    r = app.test_client().post("/v1/translate", json={"requestId": "r", "source": "fr", "target": "ff", "variety": "ngaoundere",
                                                      "segments": [{"id": "a", "text": "Votre demande a été envoyée.", "placeholders": []}]})
    assert r.status_code == 200 and no_network == []
