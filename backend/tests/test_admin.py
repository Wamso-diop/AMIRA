"""S8 : /v1/admin (natifs) : jeton, réseau, audit, mémoire admin, enregistrements ; flask export-admin."""
import csv
import io
from pathlib import Path

import pytest

from amira import create_app, db
from conftest import DEV
from gold import GOLD, rows, to_front
from tools.import_gold import import_gold

TOKEN, OLD = "jeton-admin-nouveau", "jeton-admin-ancien"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
AUDIO = b"OggS\x00fake-ogg"
BY_ID = {r["id"]: r for r in rows()}


@pytest.fixture
def admin_app(db_path, tmp_path):
    return create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_RECORDINGS_DIR": str(tmp_path / "rec"),
                       "AMIRA_ADMIN_TOKENS": f"{TOKEN},{OLD}"}, engine=None)


@pytest.fixture
def c(admin_app):
    return admin_app.test_client()


def conn_of(app):
    return db.connect(app.config["DB_PATH"])


def put_translation(c, **over):
    body = {"source": "fr", "target": "ff", "variety": "ngaoundere", "sourceMasked": "Alerte inconnue {N0}",
            "text": "<<Alerte {N0}>>", "validatedBy": "natif-1", **over}
    return c.put("/v1/admin/translations", json=body, headers=AUTH)


def translate(c, text, category=None):
    seg = {"id": "a", "text": text, "placeholders": [], **({"categoryHint": category} if category else {})}
    return c.post("/v1/translate", json={"requestId": "r", "source": "fr", "target": "ff", "variety": "ngaoundere",
                                         "segments": [seg]}).get_json()["segments"][0]


# --- accès -------------------------------------------------------------------------------

@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer faux"}, {"Authorization": TOKEN},
                                     {"Authorization": "Bearer "}, {"Authorization": "Basic " + TOKEN},
                                     {"Authorization": "Bearer " + TOKEN[:5]}, {"Authorization": "Bearer " + TOKEN + "x"}])
def test_401_sans_bon_jeton(c, headers):
    r = c.get("/v1/admin/feedback", headers=headers)
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "BAD_REQUEST"


def test_rotation_deux_jetons(c):
    assert c.get("/v1/admin/feedback", headers=AUTH).status_code == 200
    assert c.get("/v1/admin/feedback", headers={"Authorization": f"Bearer {OLD}"}).status_code == 200


def test_aucun_jeton_configure_tout_refuse(db_path):
    app = create_app({**DEV, "AMIRA_DB_PATH": db_path}, engine=None)
    assert app.test_client().get("/v1/admin/feedback", headers={"Authorization": "Bearer "}).status_code == 401


def test_hors_reseau_interne_refuse(c):
    r = c.get("/v1/admin/feedback", headers=AUTH, environ_base={"REMOTE_ADDR": "8.8.8.8"})
    assert r.status_code == 401


def test_reseaux_configurables(db_path):
    app = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ADMIN_TOKENS": TOKEN, "AMIRA_ADMIN_NETWORKS": "10.1.0.0/16"}, engine=None)
    c = app.test_client()
    assert c.get("/v1/admin/feedback", headers=AUTH).status_code == 401  # 127.0.0.1 n'est plus permis
    assert c.get("/v1/admin/feedback", headers=AUTH, environ_base={"REMOTE_ADDR": "10.1.2.3"}).status_code == 200


# --- traductions validées par un natif -----------------------------------------------------

def test_put_translation_puis_validated(admin_app, c):
    assert translate(c, "Alerte inconnue {N0}", "security_warning")["status"] == "uncertain"
    assert put_translation(c).status_code == 204
    s = translate(c, "Alerte inconnue {N0}", "security_warning")
    assert s["status"] == "validated" and s["text"] == "<<Alerte {N0}>>"
    conn = conn_of(admin_app)
    assert conn.execute("SELECT count(*) FROM unmatched").fetchone()[0] == 0  # sortie de la liste à valider
    (who, action, key, at) = conn.execute("SELECT who, action, key, at FROM audit WHERE action = 'put_translation'").fetchone()
    assert who == "natif-1" and key.startswith("fr>ff:ngaoundere:") and at
    (ref, by) = conn.execute("SELECT ref, validated_by FROM translations WHERE source_masked = 'Alerte inconnue {N0}'").fetchone()
    assert (ref, by) == ("admin", "natif-1")


@pytest.mark.parametrize("over", [
    {"validatedBy": ""},
    {"validatedBy": None},
    {"text": "<<Alerte>>"},                               # marqueur perdu
    {"text": "<<{/B0}Alerte {N0}{B0}>>", "sourceMasked": "{B0}Alerte{/B0} {N0}"},
    {"sourceMasked": "Payer 5000 FCFA", "text": "<<Payer>>"},  # garde sur la source
    {"text": "<<Alerte {N0} 5>>"},                        # garde sur la traduction
    {"source": "fr", "target": "en"},
    {"variety": "tokyo"},
    {"text": ""},
])
def test_put_translation_refusee(admin_app, c, over):
    r = put_translation(c, **over)
    assert r.status_code == 400
    assert conn_of(admin_app).execute("SELECT count(*) FROM translations WHERE ref = 'admin'").fetchone()[0] == 0


def test_import_ne_touche_jamais_l_admin(admin_app, c):
    row = BY_ID["g0015"]
    assert put_translation(c, sourceMasked=row["fr"], text="<<correction du natif>>").status_code == 204
    report = import_gold(conn_of(admin_app), GOLD, "natif-1")
    assert translate(c, row["fr"])["text"] == "<<correction du natif>>"
    assert {"direction": "fr>ff", "kept": "admin", "dropped": "g0015", "decided": False} in report["conflicts"]


def test_import_ne_supprime_pas_l_admin(admin_app, c):
    put_translation(c)
    import_gold(conn_of(admin_app), GOLD, "natif-1")
    assert translate(c, "Alerte inconnue {N0}")["status"] == "validated"


def test_export_admin_format_gold_et_aller_retour(admin_app, c, tmp_path):
    put_translation(c, sourceMasked="De {N1} vers {N0}", text="<<a {N0} b {N1}>>")
    put_translation(c, source="ff", target="en", variety=None, sourceMasked="Texte source ff", text="Text in English")
    out = tmp_path / "admin.csv"
    result = admin_app.test_cli_runner().invoke(args=["export-admin", str(out)])
    assert result.exit_code == 0, result.output
    data = list(csv.DictReader(io.StringIO(out.read_text(encoding="utf-8"))))
    assert list(data[0].keys()) == list(rows()[0].keys())  # mêmes colonnes que le gold
    by_dir = {r["notes"].split()[0]: r for r in data}
    assert (by_dir["fr>ff"]["fr"], by_dir["fr>ff"]["ff"], by_dir["fr>ff"]["n_markers"]) == ("De {V1} vers {V2}", "<<a {V2} b {V1}>>", "2")
    assert (by_dir["ff>en"]["ff"], by_dir["ff>en"]["en"]) == ("Texte source ff", "Text in English")
    assert "natif-1" in by_dir["fr>ff"]["notes"]
    # l'export se réimporte tel quel dans une base neuve
    fresh = db.connect(str(tmp_path / "neuve.sqlite3"))
    report = import_gold(fresh, out, "natif-1")
    assert report["refused"] == []
    hit = db.find_translation(fresh, "fr", "ff", "ngaoundere", db.memory_key("De {N1} vers {N0}"))
    assert hit["text"] == "<<a {N1} b {N0}>>"


# --- listes ------------------------------------------------------------------------------

def test_feedback_liste_et_resolution_auditee(admin_app, c):
    c.post("/v1/feedback", json={"segmentId": "s1", "originalMasked": "Frais : {N0}", "shown": "x", "suggestion": "y"})
    items = c.get("/v1/admin/feedback?status=pending", headers=AUTH).get_json()["items"]
    assert len(items) == 1 and items[0]["status"] == "pending" and items[0]["originalMasked"] == "Frais : {N0}"
    fid = items[0]["id"]
    assert c.post(f"/v1/admin/feedback/{fid}/resolve", json={"validatedBy": "natif-1"}, headers=AUTH).status_code == 204
    assert c.get("/v1/admin/feedback?status=pending", headers=AUTH).get_json()["items"] == []
    assert conn_of(admin_app).execute("SELECT who FROM audit WHERE action = 'resolve_feedback'").fetchone()[0] == "natif-1"
    assert conn_of(admin_app).execute("SELECT count(*) FROM translations WHERE ref = 'admin'").fetchone()[0] == 0
    assert c.post("/v1/admin/feedback/9999/resolve", json={"validatedBy": "natif-1"}, headers=AUTH).status_code == 404


def test_unmatched_les_plus_demandes_d_abord(c):
    for text, n in (("Alerte une", 1), ("Alerte deux", 3)):
        for _ in range(n):
            translate(c, text, "security_warning")
    items = c.get("/v1/admin/unmatched", headers=AUTH).get_json()["items"]
    assert [(i["textMasked"], i["requests"]) for i in items] == [("Alerte deux", 3), ("Alerte une", 1)]


# --- enregistrements des natifs -------------------------------------------------------------

def upload(c, key="k0838aeb6", data=AUDIO, mime="audio/ogg", language="ff", who="natif-1"):
    return c.put(f"/v1/admin/recordings/{key}?language={language}&validatedBy={who}", data=data,
                 headers={**AUTH, "Content-Type": mime})


def test_depot_puis_lecture(admin_app, c):
    c.post("/v1/tts", json={"text": "Votre solde est de au", "language": "ff", "segmentKey": "k0838aeb6"})
    missing = c.get("/v1/admin/recordings/missing?language=ff", headers=AUTH).get_json()["items"]
    assert [m["segmentKey"] for m in missing] == ["k0838aeb6"]
    assert upload(c).status_code == 204
    r = c.post("/v1/tts", json={"text": "Votre solde est de au", "language": "ff", "segmentKey": "k0838aeb6"})
    assert r.status_code == 200 and r.data == AUDIO and r.headers["X-Amira-Voice"] == "recorded" and r.mimetype == "audio/ogg"
    assert c.get("/v1/admin/recordings/missing?language=ff", headers=AUTH).get_json()["items"] == []
    assert conn_of(admin_app).execute("SELECT who, key FROM audit WHERE action = 'put_recording'").fetchone()[0] == "natif-1"


def test_missing_les_plus_demandes_d_abord(c):
    for key, n in (("k00000001", 1), ("k00000002", 2)):
        for _ in range(n):
            c.post("/v1/tts", json={"text": "Bonjour", "language": "ff", "segmentKey": key})
    items = c.get("/v1/admin/recordings/missing?language=ff", headers=AUTH).get_json()["items"]
    assert [(i["segmentKey"], i["requests"]) for i in items] == [("k00000002", 2), ("k00000001", 1)]


@pytest.mark.parametrize("key", ["..%2F..%2Fetc%2Fpasswd", "k0838aeb6.mp3", "K0838AEB6", "k0838aeb", "k0838aeb6x", "%2e%2e"])
def test_traversee_refusee(admin_app, c, key, tmp_path):
    r = upload(c, key=key)
    assert r.status_code in (400, 404)
    assert not any(p.is_file() for p in tmp_path.rglob("*") if p.suffix in (".ogg", ".mp3"))


@pytest.mark.parametrize("language", ["..", "de", "ff/../..", ""])
def test_langue_refusee(c, language):
    assert upload(c, language=language).status_code == 400


@pytest.mark.parametrize("mime", ["text/html", "application/octet-stream", "image/svg+xml", "audio/x-unknown", ""])
def test_mauvais_type_mime(c, mime):
    assert upload(c, mime=mime).status_code == 400


def test_audio_trop_gros(c):
    assert upload(c, data=b"\x00" * (5 * 1024 * 1024 + 1)).status_code == 413


def test_audio_vide_et_nom_obligatoires(c):
    assert upload(c, data=b"").status_code == 400
    assert upload(c, who="").status_code == 400


def test_suppression_auditee(admin_app, c):
    upload(c)
    r = c.delete("/v1/admin/recordings/k0838aeb6?language=ff&validatedBy=natif-1", headers=AUTH)
    assert r.status_code == 204
    assert c.post("/v1/tts", json={"text": "Bonjour", "language": "ff", "segmentKey": "k0838aeb6"}).status_code == 204
    assert not any(p.is_file() for p in Path(admin_app.config["RECORDINGS_DIR"]).rglob("*"))
    assert conn_of(admin_app).execute("SELECT who FROM audit WHERE action = 'delete_recording'").fetchone()[0] == "natif-1"


def test_admin_hors_contrat_public(c):
    # l'extension n'appelle jamais l'admin : pas d'en-tête CORS pour elle
    r = c.get("/v1/admin/feedback", headers={**AUTH, "Origin": "chrome-extension://abcdefghijklmnop"})
    assert "Access-Control-Allow-Origin" not in r.headers


@pytest.mark.parametrize("path,method", [("/v1/admin/translations", "put"), ("/v1/admin/feedback/1/resolve", "post")])
@pytest.mark.parametrize("payload", [[1], "texte", 5])
def test_corps_json_qui_n_est_pas_un_objet(c, path, method, payload):
    r = getattr(c, method)(path, json=payload, headers=AUTH)
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "BAD_REQUEST"
