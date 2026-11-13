"""Ajouter une langue = un dossier languages/<code>/ : le serveur en déduit sens, modèle, mémoire et variétés."""
import pytest

from amira import config, create_app, db
from amira.engine import FakeEngine
from tools import new_language
from tools.import_gold import import_gold


@pytest.fixture
def zz(tmp_path, monkeypatch):
    new_language.create("zz", "zzz_Latn", ["nord", "sud"], tmp_path)
    monkeypatch.setattr(config, "LANGUAGES_DIR", tmp_path)
    return tmp_path


def test_config_deduite_de_la_fiche(zz):
    cfg = config.load({"AMIRA_ENV": "development", "AMIRA_LANGUAGE": "zz"})
    assert cfg["TARGET"] == "zz" and cfg["LANGUAGES"] == ["fr", "en", "zz"]
    assert cfg["DIRECTIONS"] == ["fr>zz", "en>zz", "zz>fr", "zz>en"] and cfg["VARIETIES"] == ["nord", "sud"]
    assert cfg["LANG_CODES"]["zz"] == "zzz_Latn" and cfg["GOLD_PATH"] == "languages/zz/gold.csv"


def test_langue_inconnue_refusee():
    with pytest.raises(RuntimeError, match="language.json"):
        config.load({"AMIRA_ENV": "development", "AMIRA_LANGUAGE": "nope"})


def test_creation_refuse_codes_invalides_et_doublons(zz):
    for bad in ("fr", "en", "FUL", "x"):
        with pytest.raises(ValueError):
            new_language.create(bad, "x", [], zz)
    with pytest.raises(FileExistsError):
        new_language.create("zz", "zzz_Latn", [], zz)


def test_memoire_et_traduction_de_bout_en_bout(zz, tmp_path):
    """Une ligne de mémoire dans la colonne « zz » est servie validée, dans les deux sens, sans toucher au code."""
    gold = zz / "zz" / "gold.csv"
    header = gold.read_text(encoding="utf-8").strip()
    row = dict.fromkeys(header.split(","), "")
    row.update(id="g1", kind="ui", fr="Bonjour", en="Hello", zz="Mot-zz")
    gold.write_text(header + "\n" + ",".join(row[c] for c in header.split(",")) + "\n", encoding="utf-8")
    conn = db.connect(str(tmp_path / "t.sqlite3"))
    assert import_gold(conn, gold, "natif-1", "zz", "nord")["entries"] == 4
    app = create_app({"AMIRA_ENV": "development", "AMIRA_LANGUAGE": "zz", "AMIRA_ENGINE": "memory",
                      "AMIRA_DB_PATH": str(tmp_path / "t.sqlite3")}, engine=None)
    body = {"requestId": "1", "source": "fr", "target": "zz", "variety": "nord", "segments": [{"id": "s1", "text": "Bonjour", "placeholders": []}]}
    out = app.test_client().post("/v1/translate", json=body).get_json()["segments"][0]
    assert out["status"] == "validated" and out["text"] == "Mot-zz"
    back = dict(body, source="zz", target="fr", variety="")
    back["segments"][0]["text"] = "Mot-zz"
    assert app.test_client().post("/v1/translate", json=back).get_json()["segments"][0]["text"] == "Bonjour"
