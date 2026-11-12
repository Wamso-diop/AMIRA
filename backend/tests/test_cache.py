"""S11 : cache des sorties machine (mémoire vive, texte masqué), cache négatif, dédoublonnage, choix des segments."""
import logging
import sqlite3
import threading

import pytest

from amira import create_app
from amira.engine import FakeEngine
from amira.services.translator import MachineCache
from conftest import DEV

ADMIN = {"Authorization": "Bearer jeton"}


def make(db_path, engine, **env):
    return create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ENGINE": "nllb", "AMIRA_ADMIN_TOKENS": "jeton", **env}, engine=engine)


def seg(text, i, category=None):
    return {"id": i, "text": text, "placeholders": [], **({"categoryHint": category} if category else {})}


def translate(app, segments, source="fr", target="ff"):
    r = app.test_client().post("/v1/translate", json={"requestId": "r", "source": source, "target": target,
                                                      "variety": "ngaoundere", "segments": segments})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["segments"]


# un seul paquet de 2 par requête : estimation 0,1 s par segment, budget 0,25 s (2 segments tiennent),
# faux moteur de 0,2 s par appel ; ensuite il reste 0,05 s, pas de quoi lancer un autre segment
DELAY, SEG_S = 0.2, 0.1
ONE_CHUNK = {"AMIRA_ENGINE_BATCH": "2", "AMIRA_ENGINE_BUDGET_S": "0.25"}


def sent(engine):
    return [t for call in engine.calls for t in call[0]]


# --- cache positif ------------------------------------------------------------------------

def test_deuxieme_demande_servie_par_le_cache(db_path):
    engine = FakeEngine()
    app = make(db_path, engine)
    first = translate(app, [seg("Texte inconnu", "a")])
    calls = len(engine.calls)
    second = translate(app, [seg("Texte inconnu", "a")])
    assert first == second and second[0]["status"] == "machine" and second[0]["origin"] == "llm"
    assert len(engine.calls) == calls  # le moteur n'est pas rappelé


def test_cache_jamais_validated(db_path):
    app = make(db_path, FakeEngine(lambda t, *_: (f"<<{t}>>", 1.0)))
    for _ in range(3):
        assert translate(app, [seg("Texte inconnu", "a")])[0]["status"] == "machine"


def test_numerotation_N_restauree(db_path):
    engine = FakeEngine()
    app = make(db_path, engine)
    translate(app, [seg("Payer {N0} à {N1} avant {B0}demain{/B0}", "a")])
    (s,) = translate(app, [seg("Payer {N5} à {N2} avant {B0}demain{/B0}", "a")])
    assert s["status"] == "machine" and s["text"] == "<<Payer {N5} à {N2} avant {B0}demain{/B0}>>"
    assert len(engine.calls) == 1


def test_cache_par_sens(db_path):
    engine = FakeEngine()
    app = make(db_path, engine)
    translate(app, [seg("Texte inconnu", "a")], "fr", "ff")
    translate(app, [seg("Texte inconnu", "a")], "ff", "fr")
    assert len(engine.calls) == 2


def test_sensible_jamais_servi_par_le_cache(db_path):
    engine = FakeEngine()
    app = make(db_path, engine)
    assert translate(app, [seg("Texte partagé", "a", "label")])[0]["status"] == "machine"
    for category in ("security_warning", "fees"):
        (s,) = translate(app, [seg("Texte partagé", "a", category)])
        assert s["status"] == "uncertain" and s["text"] == "Texte partagé"


def test_validation_admin_prend_le_dessus(db_path):
    app = make(db_path, FakeEngine())
    assert translate(app, [seg("Texte inconnu", "a")])[0]["status"] == "machine"
    r = app.test_client().put("/v1/admin/translations", headers=ADMIN, json={
        "source": "fr", "target": "ff", "variety": "ngaoundere", "sourceMasked": "Texte inconnu",
        "text": "<<relu par le natif>>", "validatedBy": "natif-1"})
    assert r.status_code == 204
    (s,) = translate(app, [seg("Texte inconnu", "a")])
    assert s["status"] == "validated" and s["text"] == "<<relu par le natif>>"


def test_lru_limite(db_path):
    engine = FakeEngine()
    app = make(db_path, engine, AMIRA_CACHE_SIZE="2")
    for t in ("Texte a", "Texte b", "Texte a", "Texte c"):  # « a » relu : « b » est le plus ancien
        translate(app, [seg(t, "x")])
    n = len(engine.calls)
    translate(app, [seg("Texte a", "x")])
    assert len(engine.calls) == n
    translate(app, [seg("Texte b", "x")])
    assert len(engine.calls) == n + 1


def test_cache_absent_de_la_base_et_des_journaux(db_path, caplog):
    app = make(db_path, FakeEngine(lambda t, *_: (f"SORTIECACHE {t}", 0.9)))
    with caplog.at_level(logging.DEBUG):
        translate(app, [seg("Texte CANARIMASQUE", "a"), seg("CANARI-c 699123456", "b")])
        translate(app, [seg("Texte CANARIMASQUE", "a"), seg("CANARI-c 699123456", "b")])
    conn = sqlite3.connect(db_path)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    dump = " ".join(str(row) for t in tables for row in conn.execute(f"SELECT * FROM {t}"))
    assert "SORTIECACHE" not in dump and "CANARI" not in dump
    assert "SORTIECACHE" not in caplog.text and "CANARI" not in caplog.text


def test_cache_vide_au_redemarrage(db_path):
    engine = FakeEngine()
    translate(make(db_path, engine), [seg("Texte inconnu", "a")])
    translate(make(db_path, engine), [seg("Texte inconnu", "a")])  # nouvelle application = redémarrage
    assert len(engine.calls) == 2


# --- dédoublonnage --------------------------------------------------------------------------

def test_textes_identiques_traduits_une_fois(db_path):
    engine = FakeEngine()
    res = translate(make(db_path, engine), [seg("Valider {N0}", "a"), seg("Refuser maintenant", "b"), seg("valider {N3} ", "c"),
                                            seg("Valider {N0}", "d")])
    assert sorted(sent(engine)) == ["Refuser maintenant", "Valider {V1}"]
    assert [r["status"] for r in res] == ["machine"] * 4
    assert res[2]["text"] == "<<Valider {N3}>>" and res[3]["text"] == "<<Valider {N0}>>"


# --- cache négatif ---------------------------------------------------------------------------

def test_echec_repete_en_cache_negatif(db_path, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("amira.services.translator.time.monotonic", lambda: now[0])
    engine = FakeEngine(lambda t, *_: (t if "raté" in t else f"<<{t}>>", 0.9))  # « raté » revient identique : refusé
    app = make(db_path, engine)
    assert translate(app, [seg("Texte raté", "a")])[0]["status"] == "uncertain"
    assert sent(engine) == ["Texte raté", "Texte raté"]  # normal puis strict
    translate(app, [seg("Texte raté", "a")])
    assert len(engine.calls) == 2  # pas retenté pendant 10 minutes
    now[0] += 601
    translate(app, [seg("Texte raté", "a")])
    assert len(engine.calls) == 4


def test_cache_negatif_libere_les_creneaux(db_path):
    # budget d'un seul paquet de 2 : les deux premiers échouent, la requête suivante essaie les deux autres
    engine = FakeEngine(lambda t, *_: (t if "raté" in t else f"<<{t}>>", 0.9), delay=DELAY, seconds_per_segment=SEG_S)
    app = make(db_path, engine, **ONE_CHUNK)
    texts = [seg("Un raté", "a"), seg("Deux raté", "b"), seg("Trois long texte", "c"), seg("Quatre long texte", "d")]
    translate(app, texts)
    res = translate(app, texts)
    assert [r["status"] for r in res] == ["uncertain", "uncertain", "machine", "machine"]


# --- choix des segments -----------------------------------------------------------------------

BATCH = [seg("Un libellé assez long pour passer après", "a", "label"), seg("Court", "b"),
         seg("Une erreur longue de saisie du formulaire", "c", "error"), seg("Moyen texte", "d"),
         seg("Suivez cette instruction", "e", "instruction"), seg("Libellé", "f", "label")]


def test_erreurs_et_instructions_d_abord_puis_courts(db_path):
    engine = FakeEngine()
    translate(make(db_path, engine, AMIRA_ENGINE_BATCH="10"), BATCH)
    assert engine.calls[0][0] == ["Suivez cette instruction", "Une erreur longue de saisie du formulaire",
                                  "Court", "Libellé", "Moyen texte", "Un libellé assez long pour passer après"]


def test_choix_deterministe(db_path):
    orders = []
    for _ in range(3):
        engine = FakeEngine(delay=DELAY, seconds_per_segment=SEG_S)
        translate(make(db_path, engine, **ONE_CHUNK), BATCH)
        orders.append(sent(engine))
    assert orders[0] == orders[1] == orders[2] == ["Suivez cette instruction", "Une erreur longue de saisie du formulaire"]


def test_couverture_progressive(db_path):
    engine = FakeEngine(delay=DELAY, seconds_per_segment=SEG_S)
    app = make(db_path, engine, **ONE_CHUNK)
    texts = [seg(f"Texte {c}", c) for c in "abcdef"]
    counts = [sum(r["status"] == "machine" for r in translate(app, texts)) for _ in range(3)]
    assert counts == [2, 4, 6]  # chaque visite ajoute un paquet, le cache garde les précédents


# --- accès simultanés ---------------------------------------------------------------------------

def test_acces_simultanes(db_path):
    app = make(db_path, FakeEngine(delay=0.01))
    errors, results = [], []

    def go(k):
        try:
            texts = [seg(f"Texte {chr(97 + (k + j) % 6)} {{N{j}}}", str(j)) for j in range(3)]
            results.append(translate(app, texts))
        except Exception as e:  # toute exception fait échouer le test
            errors.append(e)

    threads = [threading.Thread(target=go, args=(k,)) for k in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == [] and len(results) == 12
    for res in results:
        for r in res:
            assert r["status"] in ("machine", "uncertain") and (r["status"] != "machine" or r["text"].startswith("<<"))


def test_machine_cache_seul_thread_safe():
    cache = MachineCache(size=50, negative_ttl=600)
    def work(k):
        for i in range(500):
            cache.put(("fr", "ff", f"k{(k * i) % 80}"), ("x", 0.9))
            cache.get(("fr", "ff", f"k{i % 80}"))
            cache.reject(("fr", "ff", f"n{i % 30}"))
            cache.rejected(("fr", "ff", f"n{i % 30}"))
    threads = [threading.Thread(target=work, args=(k,)) for k in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(cache) <= 50


def test_stockage_en_numerotation_canonique(db_path):
    engine = FakeEngine()
    app = make(db_path, engine)
    translate(app, [seg("Payer {N3} à {N1}", "a")])  # numérotation d'un appelant serveur
    (s,) = translate(app, [seg("Payer {N0} à {N1}", "a")])
    assert s["status"] == "machine" and s["text"] == "<<Payer {N0} à {N1}>>" and len(engine.calls) == 1


def test_accepte_en_seconde_tentative_pas_dans_le_cache_negatif(db_path):
    engine = FakeEngine(lambda t, s, g, strict: (f"<<{t}>>" if strict else t, 0.9))
    app = make(db_path, engine)
    assert translate(app, [seg("Texte inconnu", "a")])[0]["status"] == "machine"
    cache = app.extensions["amira"]["cache"]
    assert not cache.rejected(("fr", "ff", "texte inconnu"))
