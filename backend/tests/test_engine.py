"""S6 : moteur (faux moteur pour les contrôles de sortie, vrai modèle sous @pytest.mark.model)."""
import json
import logging
import time
from pathlib import Path

import pytest

from amira import create_app
from amira.engine import EngineError, FakeEngine
from conftest import DEV
from openapi_check import assert_conforms

SRC = "Votre solde est de {B0}{N0}{/B0} au {N1}."


def wrap(text, src, tgt, strict):
    return f"<<{text}>>", 0.9


def app_with(db_path, engine, **env):
    return create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ENGINE": "nllb", **env}, engine=engine)


def translate(app, texts, source="fr", target="ff", category=None):
    segs = [{"id": f"s{i}", "text": t, "placeholders": [], **({"categoryHint": category} if category else {})}
            for i, t in enumerate(texts)]
    r = app.test_client().post("/v1/translate", json={"requestId": "r1", "source": source, "target": target,
                                                      "variety": "ngaoundere", "segments": segs})
    assert_conforms(r, "/v1/translate", "post")
    assert r.status_code == 200, r.get_json()
    return r.get_json()["segments"]


def test_sortie_correcte_machine(db_path):
    engine = FakeEngine(wrap)
    (s,) = translate(app_with(db_path, engine), [SRC])
    assert s == {"id": "s0", "text": "<<" + SRC + ">>", "status": "machine", "confidence": 0.9, "origin": "llm"}


def test_le_moteur_ne_voit_que_des_V(db_path):
    engine = FakeEngine(wrap)
    translate(app_with(db_path, engine), [SRC])
    ((texts, src, tgt, strict),) = engine.calls
    assert texts == ["Votre solde est de {V1}{V2}{V3} au {V4}."] and (src, tgt, strict) == ("fr", "ff", False)


def test_sens_inverse_transmis(db_path):
    engine = FakeEngine(wrap)
    translate(app_with(db_path, engine), ["Texte inconnu"], "ff", "en")
    assert engine.calls[0][1:3] == ("ff", "en")


@pytest.mark.parametrize("name,fn", [
    ("marqueur perdu", lambda t, *_: (t.replace("{V2}", ""), 0.9)),
    ("marqueur doublé", lambda t, *_: (t + " {V4}", 0.9)),
    ("V inventé", lambda t, *_: (t + " {V9}", 0.9)),
    ("chiffre inventé", lambda t, *_: ("<<" + t + " 2>>", 0.9)),
    ("devise inventée", lambda t, *_: ("<<" + t + " FCFA>>", 0.9)),
    ("sortie vide", lambda t, *_: ("  ", 0.9)),
    ("sortie identique", lambda t, *_: (t, 0.9)),
    ("confiance basse", lambda t, *_: ("<<" + t + ">>", 0.49)),
    ("mal imbriqué", lambda t, *_: (t.replace("{V1}", "§").replace("{V3}", "{V1}").replace("§", "{V3}"), 0.9)),
])
def test_sortie_refusee_incertaine(db_path, name, fn):
    engine = FakeEngine(fn)
    (s,) = translate(app_with(db_path, engine), [SRC])
    assert s == {"id": "s0", "text": SRC, "status": "uncertain", "confidence": 0.0, "origin": "llm"}, name
    assert [c[3] for c in engine.calls] == [False, True]  # une seule seconde tentative, stricte


def test_seconde_tentative_stricte_acceptee(db_path):
    engine = FakeEngine(lambda t, s, g, strict: (("<<" + t + ">>") if strict else t.replace("{V1}", ""), 0.8))
    (s,) = translate(app_with(db_path, engine), [SRC])
    assert s["status"] == "machine" and s["text"] == "<<" + SRC + ">>"


def test_seconde_tentative_seulement_pour_les_refuses(db_path):
    engine = FakeEngine(lambda t, s, g, strict: ("<<" + t + ">>", 0.9 if "bon" in t or strict else 0.1))
    res = translate(app_with(db_path, engine), ["Texte bon", "Texte faible"])
    assert [r["status"] for r in res] == ["machine", "machine"]
    assert engine.calls[1][0] == ["Texte faible"] and engine.calls[1][3] is True


def test_seuil_plus_haut_depuis_ff(db_path):
    engine = FakeEngine(lambda t, *_: ("<<" + t + ">>", 0.6))
    assert translate(app_with(db_path, engine), ["Texte inconnu"])[0]["status"] == "machine"
    assert translate(app_with(db_path, engine), ["Texte inconnu"], "ff", "fr")[0]["status"] == "uncertain"


def test_seuils_configurables(db_path):
    engine = FakeEngine(lambda t, *_: ("<<" + t + ">>", 0.6))
    app = app_with(db_path, engine, AMIRA_MIN_CONFIDENCE="0.65")
    assert translate(app, ["Texte inconnu"])[0]["status"] == "uncertain"


def test_exception_du_moteur_sans_texte(db_path, caplog):
    def boom(t, *_):
        raise RuntimeError("CANARI-moteur " + t)

    with caplog.at_level(logging.DEBUG):
        res = translate(app_with(db_path, FakeEngine(boom)), ["Texte un", "Texte deux"])
    assert [r["status"] for r in res] == ["uncertain", "uncertain"]
    assert "CANARI" not in caplog.text and "Texte un" not in caplog.text
    assert "EngineError" in caplog.text or "RuntimeError" in caplog.text


def test_engine_error_sans_texte():
    assert str(EngineError()) == "échec du moteur"


def test_budget_depasse_segments_restants_incertains(db_path):
    engine = FakeEngine(wrap, delay=0.2)
    app = app_with(db_path, engine, AMIRA_ENGINE_BUDGET_S="0.5", AMIRA_ENGINE_BATCH="1", AMIRA_ENGINE_SEG_S="0.2")
    t0 = time.perf_counter()
    res = translate(app, [f"Texte {c}" for c in "abcdefgh"])
    elapsed = time.perf_counter() - t0
    statuses = [r["status"] for r in res]
    assert statuses[0] == "machine" and statuses[-1] == "uncertain"
    assert elapsed < 0.5 + 0.2  # jamais un paquet commencé sans le temps de le finir
    assert [r["id"] for r in res] == [f"s{i}" for i in range(8)]


def test_verrou_occupe_incertain(db_path):
    engine = FakeEngine(wrap)
    engine.busy = True  # un autre fil tient le modèle au-delà du budget
    (s,) = translate(app_with(db_path, engine, AMIRA_ENGINE_BUDGET_S="0.3"), ["Texte inconnu"])
    assert s["status"] == "uncertain"


def test_canari_refuse_jamais_au_moteur(db_path):
    engine = FakeEngine(wrap)
    res = translate(app_with(db_path, engine), ["CANARI-77 699123456", "Texte inconnu"])
    assert res[0]["status"] == "uncertain" and res[1]["status"] == "machine"
    assert all("CANARI" not in t for c in engine.calls for t in c[0])


def test_V_litteral_jamais_au_moteur(db_path):
    engine = FakeEngine(wrap)
    (s,) = translate(app_with(db_path, engine), ["Texte {V1} et {N0}"])
    assert s["status"] == "uncertain" and engine.calls == []


def test_memoire_avant_moteur(db_path):
    from gold import rows

    engine = FakeEngine(wrap)
    (s,) = translate(app_with(db_path, engine), [rows()[14]["fr"]])
    assert s["status"] == "validated" and engine.calls == []


def test_moteur_pas_pret_incertain(db_path):
    engine = FakeEngine(wrap, loaded=False)
    (s,) = translate(app_with(db_path, engine), ["Texte inconnu"])
    assert s["status"] == "uncertain" and engine.calls == []


def test_mode_memoire_sans_moteur(db_path):
    app = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ENGINE": "memory"}, engine=None)
    assert app.test_client().get("/v1/ready").status_code == 200
    assert translate(app, ["Texte inconnu"])[0]["status"] == "uncertain"


def test_ready_attend_le_moteur(db_path):
    engine = FakeEngine(wrap, loaded=False)
    client = app_with(db_path, engine).test_client()
    assert client.get("/v1/ready").status_code == 503
    engine.loaded = True
    assert client.get("/v1/ready").status_code == 200


# --- vrai modèle (lent, ignoré par défaut : pytest -m model) ----------------------------------

@pytest.mark.model
def test_vrai_modele_controle_colab():
    from amira.engine import NllbEngine

    data = json.loads((Path(__file__).parents[1] / "data" / "check_model.json").read_text(encoding="utf-8"))
    engine = NllbEngine(str(Path(__file__).parents[1] / "models" / "nllb_ff"), {"fr": "fra_Latn", "en": "eng_Latn", "ff": "fuv_Latn"})
    assert not engine.ready()
    engine.load()
    assert engine.ready()
    ((text, conf),) = engine.translate([data["control"]["source"]], "fr", "ff")
    assert text == data["control"]["colab"] and 0 < conf <= 1
    ((back, conf2),) = engine.translate([text], "ff", "fr", strict=True)
    assert back and 0 < conf2 <= 1


def test_echec_de_chargement_journalise(tmp_path, caplog):
    from amira.engine import from_config

    with caplog.at_level(logging.ERROR):
        engine = from_config({"ENGINE": "nllb", "MODEL_DIR": str(tmp_path / "absent"), "LANG_CODES": {}})
        assert engine.loader is None  # rien n'est chargé avant le premier ready() (flask export-admin, purge…)
        assert not engine.ready()
        engine.loader.join(timeout=60)
    assert not engine.ready()
    assert "chargement du modèle impossible" in caplog.text


@pytest.mark.parametrize("name,fn", [
    ("sortie vide", lambda t, *_: ("", 0.9)),
    ("espaces seuls", lambda t, *_: ("   ", 0.9)),
    ("identique à la casse près", lambda t, *_: (t.upper() + " .", 0.9)),
    ("chiffre inventé", lambda t, *_: ("<<" + t + " 3>>", 0.9)),
    ("marqueur inventé", lambda t, *_: ("<<" + t + " {V1}>>", 0.9)),
])
def test_sortie_refusee_sans_marqueur_source(db_path, name, fn):
    (s,) = translate(app_with(db_path, FakeEngine(fn)), ["Texte inconnu"])
    assert s["status"] == "uncertain" and s["text"] == "Texte inconnu", name
