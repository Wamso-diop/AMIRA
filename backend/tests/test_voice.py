"""S8 : /v1/tts (enregistrement d'un natif, sinon 204) et segmentKey identique au front."""
import json
from pathlib import Path

import pytest

from amira import create_app, db
from amira.services.voice import segment_key
from conftest import DEV
from openapi_check import assert_conforms

PAIRS = json.loads((Path(__file__).parent / "fixtures" / "segment_keys.json").read_text(encoding="utf-8"))["pairs"]
AUDIO = b"ID3\x03\x00fake-mp3-bytes"
EXT = "chrome-extension://abcdefghijklmnop"


@pytest.mark.parametrize("pair", PAIRS, ids=[p["key"] for p in PAIRS])
def test_segment_key_identique_au_front(pair):
    assert segment_key(pair["text"]) == pair["key"]


def test_fixture_couvre_les_cas_demandes():
    texts = " ".join(p["text"] for p in PAIRS)
    assert len(PAIRS) >= 10 and "{B0}" in texts and "{/B0}" in texts and "{E0}" in texts
    assert any(ord(c) > 0xFFFF for c in texts)  # émoji hors BMP : unités UTF-16, pas points de code
    assert any(c in texts for c in "ɓɗƴŋ") and any(c in texts for c in "ƁƊƳŊ")


@pytest.fixture
def voice_app(db_path, tmp_path):
    return create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_RECORDINGS_DIR": str(tmp_path / "rec")}, engine=None)


def add_recording(app, key="k0838aeb6", language="ff", data=AUDIO, mime="audio/mpeg"):
    rec = Path(app.config["RECORDINGS_DIR"])
    rec.mkdir(parents=True, exist_ok=True)
    path = rec / f"{key}.{language}.mp3"
    path.write_bytes(data)
    conn = db.connect(app.config["DB_PATH"])
    conn.execute("INSERT INTO recordings VALUES (?, ?, ?, ?, 'natif-1', '2026-01-01')", (key, language, str(path), mime))
    conn.commit()
    return path


def tts(app, **body):
    r = app.test_client().post("/v1/tts", json={"text": "Votre solde est de au", "language": "ff", "speed": 1, **body},
                               headers={"Origin": EXT})
    assert_conforms(r, "/v1/tts", "post")
    return r


def test_enregistrement_natif(voice_app):
    add_recording(voice_app)
    r = tts(voice_app, segmentKey="k0838aeb6")
    assert r.status_code == 200 and r.data == AUDIO and r.mimetype == "audio/mpeg"
    assert r.headers["X-Amira-Voice"] == "recorded"
    assert "X-Amira-Voice" in r.headers["Access-Control-Expose-Headers"]


def test_enregistrement_d_une_autre_langue_ignore(voice_app):
    add_recording(voice_app, language="fr")
    assert tts(voice_app, segmentKey="k0838aeb6").status_code == 204


def test_sans_enregistrement_204_et_liste_a_enregistrer(voice_app):
    for _ in range(3):
        r = tts(voice_app, segmentKey="k12345678")
        assert r.status_code == 204 and r.data == b""
    rows = db.connect(voice_app.config["DB_PATH"]).execute("SELECT segment_key, language, text, requests FROM missing_audio").fetchall()
    assert [tuple(r) for r in rows] == [("k12345678", "ff", "Votre solde est de au", 3)]


def test_sans_cle_204_sans_rien_noter(voice_app):
    assert tts(voice_app).status_code == 204
    assert db.connect(voice_app.config["DB_PATH"]).execute("SELECT count(*) FROM missing_audio").fetchone()[0] == 0


def test_fichier_disparu_204(voice_app):
    add_recording(voice_app).unlink()
    assert tts(voice_app, segmentKey="k0838aeb6").status_code == 204


def test_marqueurs_retires_avant_stockage(voice_app):
    tts(voice_app, text="Payer {B0}{N0}{/B0} maintenant", segmentKey="k12345678")
    (text,) = db.connect(voice_app.config["DB_PATH"]).execute("SELECT text FROM missing_audio").fetchone()
    assert text == "Payer maintenant"


def test_garde_texte_refuse_204_rien_stocke(voice_app):
    r = tts(voice_app, text="CANARI-tts 699123456", segmentKey="k12345678")
    assert r.status_code == 204
    conn = db.connect(voice_app.config["DB_PATH"])
    assert conn.execute("SELECT count(*) FROM missing_audio").fetchone()[0] == 0
    assert db.counter(conn, "unmasked_total") == 1


@pytest.mark.parametrize("body", [
    {"text": "", "language": "ff"},
    {"text": "{N0} {B0}{/B0}", "language": "ff"},
    {"text": "Bonjour", "language": "de"},
    {"text": "Bonjour"},
    {"text": 5, "language": "ff"},
    {"text": "Bonjour", "language": "ff", "segmentKey": "../../etc/passwd"},
    {"text": "Bonjour", "language": "ff", "segmentKey": "K0838AEB6"},
    {"text": "Bonjour", "language": "ff", "speed": "vite"},
])
def test_requete_invalide(voice_app, body):
    r = voice_app.test_client().post("/v1/tts", json=body)
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "BAD_REQUEST"
    assert_conforms(r, "/v1/tts", "post")


def test_voix_desactivee(db_path):
    app = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_TTS_ENABLED": "false"}, engine=None)
    r = app.test_client().post("/v1/tts", json={"text": "Bonjour", "language": "ff"})
    assert r.status_code == 400
