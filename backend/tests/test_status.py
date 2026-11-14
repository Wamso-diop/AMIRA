"""S7 : statuts honnêtes. validated = mémoire relue par un natif ; sensible = mémoire seule (P2, P3)."""
import pytest

from amira import create_app, db
from amira.engine import FakeEngine
from conftest import DEV
from gold import rows, to_front
from openapi_check import assert_conforms

BY_ID = {r["id"]: r for r in rows()}


def confident(t, *_):
    return f"<<{t}>>", 1.0  # même avec une confiance maximale


def app_with(db_path, engine):
    return create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ENGINE": "m2m100"}, engine=engine)


def post(app, segments, source="fr", target="ff"):
    r = app.test_client().post("/v1/translate", json={"requestId": "r", "source": source, "target": target,
                                                      "variety": "ngaoundere", "segments": segments})
    assert r.status_code == 200
    assert_conforms(r, "/v1/translate", "post")
    return r.get_json()["segments"]


def seg(text, i="s", category=None):
    return {"id": i, "text": text, "placeholders": [], **({"categoryHint": category} if category else {})}


@pytest.mark.parametrize("category", ["security_warning", "fees"])
@pytest.mark.parametrize("source,target", [("fr", "ff"), ("en", "ff"), ("ff", "fr"), ("ff", "en")])
def test_sensible_sans_memoire_jamais_au_moteur(db_path, category, source, target):
    spy = FakeEngine(confident)
    (s,) = post(app_with(db_path, spy), [seg("Ne communiquez jamais votre code {N0}", category=category)], source, target)
    assert spy.calls == []
    assert s["status"] == "uncertain" and s["text"] == "Ne communiquez jamais votre code {N0}"


def test_sensible_melange_au_lot(db_path):
    spy = FakeEngine(confident)
    res = post(app_with(db_path, spy), [seg("Texte ordinaire", "a"), seg("Alerte inconnue", "b", "security_warning"),
                                        seg("Frais inconnus {N0}", "c", "fees")])
    assert [r["status"] for r in res] == ["machine", "uncertain", "uncertain"]
    assert spy.calls and all(t == "Texte ordinaire" for c in spy.calls for t in c[0])


def test_sensible_avec_memoire_valide_sans_moteur(db_path):
    spy = FakeEngine(confident)
    (s,) = post(app_with(db_path, spy), [seg(to_front(BY_ID["g0077"]["fr"]), category="security_warning")])
    assert s["status"] == "validated" and s["origin"] == "memory" and spy.calls == []


def test_validated_impossible_sans_memoire(db_path):
    # le moteur le plus sûr de lui ne produit jamais « validated »
    res = post(app_with(db_path, FakeEngine(confident)), [seg(f"Texte {c}", c) for c in "abcd"])
    assert {r["status"] for r in res} == {"machine"} and {r["origin"] for r in res} == {"llm"}


def test_validated_seulement_avec_origin_memory(db_path):
    gold = [seg(to_front(BY_ID[i]["fr"]), i) for i in ("g0015", "g0035", "g0077")]
    res = post(app_with(db_path, FakeEngine(confident)), gold + [seg("Texte inconnu", "x")])
    for r in res:
        assert (r["status"] == "validated") == (r["origin"] == "memory")
        assert r["status"] != "validated" or r["confidence"] == 1.0


def test_memoire_videe_plus_de_validated(db_path):
    conn = db.connect(db_path)
    conn.execute("DELETE FROM translations")
    conn.commit()
    res = post(app_with(db_path, FakeEngine(confident)), [seg(to_front(BY_ID["g0015"]["fr"]))])
    assert res[0]["status"] == "machine"


def test_parcours_complet_contre_openapi(db_path):
    """Lot mixte de 40 : mémoire, moteur, refus du moteur, garde, sensible, incertain. Chaque réponse est validée."""
    engine = FakeEngine(lambda t, *_: (f"<<{t}>>", 0.9 if "bon" in t else 0.2))
    gold = [seg(to_front(r["fr"]), r["id"]) for r in rows()[:20]]
    others = [seg(f"Texte bon {chr(97 + i)}", f"m{i}") for i in range(8)]  # pas de chiffre : la garde
    weak = [seg(f"Texte faible {chr(97 + i)}", f"w{i}") for i in range(4)]
    refused = [seg(f"Payer {i} FCFA", f"r{i}") for i in range(4)]
    sensitive = [seg(f"Alerte {chr(97 + i)}", f"x{i}", "security_warning") for i in range(4)]
    batch = gold + others + weak + refused + sensitive
    assert len(batch) == 40
    res = post(app_with(db_path, engine), batch)
    assert [r["id"] for r in res] == [s["id"] for s in batch]
    status = {r["id"]: r["status"] for r in res}
    assert all(status[s["id"]] == "validated" for s in gold)
    assert all(status[s["id"]] == "uncertain" for s in weak + refused + sensitive)
    assert any(status[s["id"]] == "machine" for s in others)  # dans le budget de 6 s
