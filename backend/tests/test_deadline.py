"""Correctif : une requête ne dépasse jamais le budget (le front coupe à 8 s), quelle que soit la longueur des textes."""
import time

import pytest

import amira.engine as engine_mod
from amira import create_app
from amira.engine import Engine, FakeEngine
from conftest import DEV
from real_engine import real_engine


def engine_with_fake_generate(monkeypatch, per_text_s, seen):
    """Engine « chargé », dont generate() est remplacé : durée proportionnelle au nombre de textes."""
    e = Engine("absent", {"fr": "fr", "ff": "ff"}, seconds_per_segment=0.01)
    e._tok, e._model = object(), object()

    def fake_generate(tok, model, texts, src, tgt, strict, max_time=None):
        seen.append(max_time)
        time.sleep(per_text_s * len(texts))
        return [(f"<<{t}>>", 0.9) for t in texts]

    monkeypatch.setattr(engine_mod, "generate", fake_generate)
    return e


def test_le_moteur_recoit_le_temps_restant(monkeypatch):
    seen = []
    e = engine_with_fake_generate(monkeypatch, 0.0, seen)
    deadline = time.perf_counter() + 2.0
    e.translate(["a"], "fr", "ff", deadline=deadline)
    assert seen[0] is not None and 1.9 < seen[0] <= 2.0  # plafond dur transmis à generate (max_time)


def test_echeance_passee_aucune_generation(monkeypatch):
    seen = []
    e = engine_with_fake_generate(monkeypatch, 0.0, seen)
    with pytest.raises(TimeoutError):
        e.translate(["a"], "fr", "ff", deadline=time.perf_counter() - 0.01)
    assert seen == []


def test_estimation_remonte_aussitot(monkeypatch):
    e = engine_with_fake_generate(monkeypatch, 0.05, [])
    e.translate(["a", "b"], "fr", "ff")
    assert e.seconds_per_segment >= 0.045  # mesuré : 0,05 s par segment, au lieu des 0,01 estimées


def test_estimation_redescend_doucement(monkeypatch):
    e = engine_with_fake_generate(monkeypatch, 0.0, [])
    e.seconds_per_segment = 1.0
    e.translate(["a"], "fr", "ff")
    assert 0.4 < e.seconds_per_segment < 1.0


def test_tentative_stricte_comptee_double(monkeypatch):
    e = engine_with_fake_generate(monkeypatch, 0.04, [])
    e.translate(["a"], "fr", "ff", strict=True)  # faisceau de 8 : environ deux fois le coût
    assert 0.015 < e.seconds_per_segment < 0.03


def test_paquet_dimensionne_sur_le_temps_restant(db_path):
    # 0,1 s estimées par segment, budget 0,25 s : un paquet de 2 au plus (et non ENGINE_BATCH=4)
    engine = FakeEngine(delay=0.2, seconds_per_segment=0.1)
    app = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ENGINE": "m2m100", "AMIRA_ENGINE_BATCH": "4",
                      "AMIRA_ENGINE_BUDGET_S": "0.25"}, engine=engine)
    t0 = time.perf_counter()
    app.test_client().post("/v1/translate", json={"requestId": "r", "source": "fr", "target": "ff", "variety": "ngaoundere",
                                                  "segments": [{"id": c, "text": f"Texte {c}", "placeholders": []} for c in "abcd"]})
    assert [len(c[0]) for c in engine.calls] == [2]
    assert time.perf_counter() - t0 < 0.25 + 0.15


@pytest.mark.model
def test_vrai_modele_phrases_longues_sous_8_s(db_path):
    e = real_engine()
    e.load()
    app = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ENGINE": "m2m100"}, engine=e)
    long = ["Pour finaliser votre demande d'ouverture de compte, veuillez vérifier les informations saisies dans le formulaire.",
            "Les virements effectués après la fermeture des services ne seront traités qu'au prochain jour ouvrable.",
            "Vous pouvez consulter l'historique complet de vos opérations depuis votre espace personnel sécurisé.",
            "Le service client reste disponible pour répondre à toutes vos questions sur l'application mobile."] * 7
    for _ in range(2):  # la seconde requête profite de l'estimation mesurée par la première
        t0 = time.perf_counter()
        r = app.test_client().post("/v1/translate", json={"requestId": "r", "source": "fr", "target": "ff", "variety": "ngaoundere",
                                                          "segments": [{"id": str(i), "text": t + f" Cas{chr(97 + i % 26)}{chr(97 + i // 26)}.", "placeholders": []}
                                                                       for i, t in enumerate(long)]})
        elapsed = time.perf_counter() - t0
        print(f"\n28 phrases longues : {elapsed:.2f} s, machine {sum(s['status'] == 'machine' for s in r.get_json()['segments'])}")
        assert r.status_code == 200 and elapsed < 7.0  # le front coupe à 8 s


def test_echeance_transmise_au_moteur(db_path):
    engine = FakeEngine()
    app = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ENGINE": "m2m100", "AMIRA_ENGINE_BUDGET_S": "6"}, engine=engine)
    t0 = time.perf_counter()
    app.test_client().post("/v1/translate", json={"requestId": "r", "source": "fr", "target": "ff", "variety": "ngaoundere",
                                                  "segments": [{"id": "a", "text": "Texte inconnu", "placeholders": []}]})
    (deadline,) = engine.deadlines
    assert deadline is not None and t0 + 5.5 < deadline <= time.perf_counter() + 6


def test_tentative_stricte_planifiee_double(db_path):
    # 2 sorties refusées en 0,05 s ; il reste ~0,25 s : 1 seul segment strict tient (0,2 s), pas 2
    engine = FakeEngine(lambda t, s, g, strict: (t, 0.9), delay=0.05, seconds_per_segment=0.1)
    app = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ENGINE": "m2m100", "AMIRA_ENGINE_BATCH": "4",
                      "AMIRA_ENGINE_BUDGET_S": "0.3"}, engine=engine)
    app.test_client().post("/v1/translate", json={"requestId": "r", "source": "fr", "target": "ff", "variety": "ngaoundere",
                                                  "segments": [{"id": c, "text": f"Texte {c}", "placeholders": []} for c in "ab"]})
    assert [(len(c[0]), c[3]) for c in engine.calls] == [(2, False), (1, True)]
