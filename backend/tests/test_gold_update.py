"""Mise à jour du gold sans redémarrage, tolérance d'écriture, fin de segment non traduite, nombres jamais traduits."""
import csv
import os
import shutil

import pytest

from amira import create_app, db
from conftest import DEV
from gold import GOLD, rows, to_front
from tools.import_gold import import_gold

BY_ID = {r["id"]: r for r in rows()}


def translate(app, text, source="fr", target="ff"):
    body = {"requestId": "r1", "source": source, "target": target, "variety": "ngaoundere",
            "segments": [{"id": "s1", "text": text, "placeholders": []}]}
    r = app.test_client().post("/v1/translate", json=body)
    assert r.status_code == 200, r.get_json()
    return r.get_json()["segments"][0]


# --- tolérance ----------------------------------------------------------------------

def test_apostrophe_typographique_et_espaces(gold_app):
    row = BY_ID["g0049"]  # contient une apostrophe droite
    s = translate(gold_app, "  " + row["fr"].replace("'", "’").upper() + "  ")
    assert s["status"] == "validated" and s["text"] == row["ff"]


def test_espace_avant_les_deux_points(gold_app):
    row = BY_ID["g0090"]  # « … : … » dans le CSV
    s = translate(gold_app, row["fr"].replace(" : ", ": "))
    assert s["status"] == "validated" and s["text"] == row["ff"]
    s = translate(gold_app, row["fr"].replace(" : ", " : "))
    assert s["status"] == "validated"


def test_points_de_suspension(gold_app):
    row = BY_ID["g0103"]
    s = translate(gold_app, row["fr"].replace("…", "..."))
    assert s["status"] == "validated" and s["text"] == row["ff"]


# --- fin de segment gardée telle quelle (numéros, codes) ------------------------------

def test_fin_avec_marqueur_gardee_intacte(gold_app):
    row = BY_ID["g0035"]  # entrée sans marqueur : le numéro n'est jamais traduit
    s = translate(gold_app, row["fr"].strip() + " : CM {N0}")
    assert s == {"id": "s1", "text": row["ff"].strip() + " : CM {N0}", "status": "validated",
                 "confidence": 1.0, "origin": "memory"}


def test_salutation_suivie_d_un_nom_masque(gold_app):
    row = BY_ID["g0032"]
    s = translate(gold_app, row["fr"].strip() + ", {N0} !")
    assert s["status"] == "validated" and s["text"] == row["ff"].strip() + ", {N0} !"


def test_marqueurs_de_la_fin_non_renumerotes(gold_app):
    row = BY_ID["g0106"]  # Total
    s = translate(gold_app, row["fr"] + " : {N3}")
    assert s["status"] == "validated" and s["text"] == row["ff"] + " : {N3}"


def test_fin_avec_des_mots_pas_decoupee(gold_app):
    # un mot ordinaire dans la fin resterait en français : pas de traduction partielle
    row = BY_ID["g0035"]
    assert translate(gold_app, row["fr"].strip() + " : principal {N0}")["status"] == "uncertain"


def test_fin_sans_marqueur_pas_decoupee(gold_app):
    row = BY_ID["g0035"]
    assert translate(gold_app, row["fr"].strip() + " : CM")["status"] == "uncertain"


# --- nombres ------------------------------------------------------------------------

NUMBER_IDS = ["g0107", "g0108"] + [f"g0{i}" for i in range(168, 184)]


def test_les_nombres_ne_sont_pas_importes(tmp_path):
    report = import_gold(db.connect(str(tmp_path / "t.sqlite3")), GOLD, "natif-1")
    assert sorted(r["id"] for r in report["refused"] if r["reason"] == "nombre") == NUMBER_IDS


@pytest.mark.parametrize("rid", ["g0169", "g0107"])
def test_un_nombre_ecrit_en_lettres_n_est_pas_traduit(gold_app, rid):
    assert translate(gold_app, BY_ID[rid]["fr"])["status"] == "uncertain"
    assert translate(gold_app, BY_ID[rid]["ff"], "ff", "fr")["status"] == "uncertain"


# --- rechargement automatique du CSV --------------------------------------------------

@pytest.fixture
def live(tmp_path):
    path = tmp_path / "gold.csv"
    shutil.copyfile(GOLD, path)
    app = create_app({**DEV, "AMIRA_DB_PATH": str(tmp_path / "a.sqlite3"),
                      "AMIRA_GOLD_PATH": str(path), "AMIRA_GOLD_VALIDATOR": "natif-1"}, engine=None)
    return app, path


def rewrite(path, change):
    with open(path, encoding="utf-8-sig", newline="") as f:
        data = list(csv.DictReader(f))
    fields = list(data[0])
    change(data)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(data)
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))  # date de modification qui change à coup sûr


def test_ligne_ajoutee_servie_sans_redemarrer(live):
    app, path = live
    new_fr = "Texte ajouté par le natif"
    ff = BY_ID["g0015"]["ff"]
    assert translate(app, BY_ID["g0015"]["fr"])["status"] == "validated"  # import au premier appel
    assert translate(app, new_fr)["status"] == "uncertain"
    rewrite(path, lambda d: d.append({**{k: "" for k in d[0]}, "id": "g9999", "kind": "ui", "fr": new_fr, "ff": ff, "n_markers": "0"}))
    s = translate(app, new_fr)
    assert s["status"] == "validated" and s["text"] == ff


def test_traduction_corrigee_et_ligne_retiree(live):
    app, path = live
    a, b = BY_ID["g0015"], BY_ID["g0097"]
    assert translate(app, a["fr"])["text"] == a["ff"]

    def change(d):
        d[:] = [r for r in d if r["id"] != b["id"]]
        next(r for r in d if r["id"] == a["id"])["ff"] = b["ff"]
    rewrite(path, change)
    assert translate(app, a["fr"])["text"] == b["ff"]
    assert translate(app, b["fr"])["status"] == "uncertain"


def test_csv_illisible_garde_l_ancienne_memoire(live, caplog):
    app, path = live
    row = BY_ID["g0015"]
    assert translate(app, row["fr"])["status"] == "validated"
    rewrite(path, lambda d: d.__setitem__(0, {**d[0], "n_markers": "un"}))
    assert translate(app, row["fr"])["status"] == "validated"
    assert row["ff"] not in caplog.text and row["fr"] not in caplog.text  # jamais de texte dans le journal


def test_sans_relecteur_pas_de_rechargement(tmp_path):
    path = tmp_path / "gold.csv"
    shutil.copyfile(GOLD, path)
    app = create_app({**DEV, "AMIRA_DB_PATH": str(tmp_path / "a.sqlite3"), "AMIRA_GOLD_PATH": str(path)}, engine=None)
    assert translate(app, BY_ID["g0015"]["fr"])["status"] == "uncertain"
    assert db.connect(str(tmp_path / "a.sqlite3")).execute("SELECT COUNT(*) FROM translations").fetchone()[0] == 0
