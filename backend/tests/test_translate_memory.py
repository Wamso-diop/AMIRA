"""S5 : /v1/translate avec la mémoire seule (forme → garde → mémoire → sensible → incertain)."""
import logging
import sqlite3

import pytest

from amira import db
from gold import rows, to_front
from openapi_check import assert_conforms

BY_ID = {r["id"]: r for r in rows()}
UNKNOWN = "Texte que la mémoire ne connaît pas"


def seg(text, i="s1", category=None):
    s = {"id": i, "text": text, "placeholders": []}
    if category:
        s["categoryHint"] = category
    return s


def req(segments, source="fr", target="ff", variety="ngaoundere"):
    return {"requestId": "9f1c2a7b3d4e5f60", "source": source, "target": target, "variety": variety, "segments": segments}


def post(app, body):
    r = app.test_client().post("/v1/translate", json=body)
    assert_conforms(r, "/v1/translate", "post")
    return r


def out(app, body):
    r = post(app, body)
    assert r.status_code == 200, r.get_json()
    return r.get_json()["segments"]


# --- mémoire ---------------------------------------------------------------------

@pytest.mark.parametrize("src,tgt", [("fr", "ff"), ("en", "ff"), ("ff", "fr"), ("ff", "en")])
def test_quatre_sens_depuis_la_memoire(gold_app, src, tgt):
    row = BY_ID["g0035"]
    (s,) = out(gold_app, req([seg(to_front(row[src]))], src, tgt))
    assert s == {"id": "s1", "text": to_front(row[tgt]), "status": "validated", "confidence": 1.0, "origin": "memory"}


def test_reponse_complete(gold_app):
    body = post(gold_app, req([seg(BY_ID["g0015"]["fr"])])).get_json()
    assert body["requestId"] == "9f1c2a7b3d4e5f60" and body["engineVersion"] and body["latencyMs"] >= 0


def test_casse_espaces_et_ponctuation(gold_app):
    row = BY_ID["g0077"]
    text = "  " + to_front(row["fr"]).upper().rstrip(".") + " !"  # {N0} reste {N0} en majuscules
    (s,) = out(gold_app, req([seg(text)]))
    assert s["status"] == "validated" and s["text"] == to_front(row["ff"])


def test_marqueurs_renumerotes(gold_app):
    row = BY_ID["g0035"]
    (s,) = out(gold_app, req([seg(to_front(row["fr"]).replace("{N0}", "{N4}"))]))
    assert s["status"] == "validated" and s["text"] == to_front(row["ff"]).replace("{N0}", "{N4}")


def test_reperes_B_exiges(gold_app):
    # un segment balisé n'est servi que par une entrée qui a les mêmes repères
    row = BY_ID["g0035"]
    (s,) = out(gold_app, req([seg("{B0}" + to_front(row["fr"]) + "{/B0}")]))
    assert s["status"] == "uncertain" and s["origin"] == "llm"


def test_variete_ignoree_vers_fr(gold_app):
    row = BY_ID["g0015"]
    (s,) = out(gold_app, req([seg(row["ff"])], "ff", "fr", "garoua"))
    assert s["status"] == "validated" and s["text"] == row["fr"]


def test_variete_comptee_vers_ff(gold_app):
    (s,) = out(gold_app, req([seg(BY_ID["g0015"]["fr"])], variety="garoua"))
    assert s["status"] == "uncertain"  # la mémoire ne connaît que ngaoundere


def test_variete_nulle_vers_ff_prend_la_premiere(gold_app):
    (s,) = out(gold_app, req([seg(BY_ID["g0015"]["fr"])], variety=None))
    assert s["status"] == "validated"


def test_entree_aux_marqueurs_abimes_ignoree(gold_app, db_path, caplog):
    conn = db.connect(db_path)
    key = db.memory_key("Payer {N0} maintenant")
    conn.execute("INSERT INTO translations VALUES ('fr', 'ff', 'ngaoundere', ?, 'Payer {N0} maintenant', 'sans marqueur', "
                 "'ui', 'natif-1', 'test', '2026-01-01')", (key,))
    conn.commit()
    with caplog.at_level(logging.WARNING):
        (s,) = out(gold_app, req([seg("Payer {N0} maintenant")]))
    assert s["status"] == "uncertain" and s["text"] == "Payer {N0} maintenant"
    assert db.counter(db.connect(db_path), "memory_bad_markers") == 1
    assert "Payer" not in caplog.text and "mémoire" in caplog.text


# --- ordre et forme de la réponse ---------------------------------------------------------

def test_un_segment_par_segment_meme_ordre(gold_app):
    segments = [seg(UNKNOWN, "a"), seg(BY_ID["g0015"]["fr"], "b"), seg("Payer 500 FCFA", "c"),
                seg(UNKNOWN, "d", "security_warning"), seg(BY_ID["g0035"]["fr"].replace("{V1}", "{N0}"), "e")]
    res = out(gold_app, req(segments))
    assert [s["id"] for s in res] == ["a", "b", "c", "d", "e"]
    assert [s["status"] for s in res] == ["uncertain", "validated", "uncertain", "uncertain", "validated"]


def test_inconnu_incertain_avec_le_texte_source(gold_app):
    (s,) = out(gold_app, req([seg(UNKNOWN)]))
    assert s == {"id": "s1", "text": UNKNOWN, "status": "uncertain", "confidence": 0.0, "origin": "llm"}


# --- catégories sensibles ----------------------------------------------------------------

@pytest.mark.parametrize("category", ["security_warning", "fees"])
def test_sensible_sans_memoire_va_dans_unmatched(gold_app, db_path, category):
    for _ in range(2):
        (s,) = out(gold_app, req([seg(UNKNOWN + " {N0}", category=category)]))
        assert s["status"] == "uncertain" and s["text"] == UNKNOWN + " {N0}"
    (row,) = db.connect(db_path).execute("SELECT text_masked, requests, variety FROM unmatched").fetchall()
    assert tuple(row) == (UNKNOWN + " {N0}", 2, "ngaoundere")


def test_sensible_avec_memoire_valide(gold_app):
    (s,) = out(gold_app, req([seg(BY_ID["g0077"]["fr"].replace("{V1}", "{N0}"), category="security_warning")]))
    assert s["status"] == "validated"


def test_non_sensible_inconnu_pas_dans_unmatched(gold_app, db_path):
    out(gold_app, req([seg(UNKNOWN, category="label")]))
    assert db.connect(db_path).execute("SELECT count(*) FROM unmatched").fetchone()[0] == 0


def test_categorie_inconnue_ignoree(gold_app):
    (s,) = out(gold_app, req([seg(BY_ID["g0015"]["fr"], category="autre")]))
    assert s["status"] == "validated"


# --- garde ---------------------------------------------------------------------------

CANARI = "CANARI-4b1d 699123456 jean.canari@exemple.cm"


def dump_db(path):
    conn = sqlite3.connect(path)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    return " ".join(str(row) for t in tables for row in conn.execute(f"SELECT * FROM {t}"))


@pytest.mark.parametrize("category", [None, "security_warning"])
def test_canari_refuse_nulle_part(gold_app, db_path, caplog, category):
    with caplog.at_level(logging.DEBUG):
        res = out(gold_app, req([seg(CANARI, "x", category), seg(BY_ID["g0015"]["fr"], "y")]))
    assert res[0] == {"id": "x", "text": CANARI, "status": "uncertain", "confidence": 0.0, "origin": "llm"}
    assert res[1]["status"] == "validated"  # le reste du lot continue
    assert "CANARI" not in dump_db(db_path) and "699123456" not in dump_db(db_path)
    assert "CANARI" not in caplog.text
    assert db.counter(db.connect(db_path), "unmasked_total") == 1


def test_garde_avant_la_memoire(gold_app, db_path):
    # même une entrée de mémoire ne sert jamais un texte refusé par la garde
    conn = db.connect(db_path)
    conn.execute("INSERT INTO translations VALUES ('fr', 'ff', 'ngaoundere', ?, 'x', 'y', 'ui', 'natif-1', 'test', 'z')",
                 (db.memory_key("Payer 5 FCFA"),))
    conn.commit()
    (s,) = out(gold_app, req([seg("Payer 5 FCFA")]))
    assert s["status"] == "uncertain" and s["text"] == "Payer 5 FCFA"


# --- sens et langues -------------------------------------------------------------------

@pytest.mark.parametrize("src,tgt", [("fr", "en"), ("en", "fr"), ("ff", "ff"), ("fr", "fr"), ("de", "ff"), ("fr", "de")])
def test_sens_refuses(gold_app, src, tgt):
    r = post(gold_app, req([seg(UNKNOWN)], src, tgt))
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "UNSUPPORTED_LANGUAGE"


def test_auto_detecte_le_francais(gold_app):
    row = BY_ID["g0077"]
    (s,) = out(gold_app, req([seg(to_front(row["fr"]))], "auto"))
    assert s["status"] == "validated"


def test_auto_detecte_l_anglais(gold_app):
    row = BY_ID["g0077"]
    (s,) = out(gold_app, req([seg(to_front(row["en"]))], "auto"))
    assert s["status"] == "validated" and s["text"] == to_front(row["ff"])


def test_auto_indecidable(gold_app):
    r = post(gold_app, req([seg("Xyz")], "auto"))
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "UNSUPPORTED_LANGUAGE"


# --- forme de la requête ------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    req([]),
    req([seg(UNKNOWN, str(i)) for i in range(41)]),
    req([seg("x" * 1001)]),
    req([{"id": 1, "text": "a", "placeholders": []}]),
    req([{"id": "a", "placeholders": []}]),
    req(["pas un objet"]),
    req([seg(UNKNOWN)], variety="tokyo"),
    {"source": "fr", "target": "ff"},
    [1, 2],
])
def test_requete_mal_formee(gold_app, body):
    r = post(gold_app, body)
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "BAD_REQUEST"


def test_corps_non_json(gold_app):
    r = gold_app.test_client().post("/v1/translate", data="pas du json", content_type="text/plain")
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "BAD_REQUEST"


def test_40_segments_et_1000_caracteres_acceptes(gold_app):
    res = out(gold_app, req([seg("x" * 1000, str(i)) for i in range(40)]))
    assert len(res) == 40


def test_auto_ignore_les_textes_refuses(gold_app):
    # un segment refusé par la garde ne pèse pas dans la détection
    row = BY_ID["g0077"]
    refused = seg("The 5 of the and the to the you the your the", "x")
    res = out(gold_app, req([refused, seg(to_front(row["fr"]), "y")], "auto"))
    assert res[1]["status"] == "validated" and res[1]["text"] == to_front(row["ff"])


@pytest.mark.parametrize("category", [{}, [], 5, "SECURITY_WARNING"])
def test_categorie_non_texte(gold_app, category):
    s = dict(seg(UNKNOWN), categoryHint=category)
    (res,) = out(gold_app, req([s]))
    assert res["status"] == "uncertain"
