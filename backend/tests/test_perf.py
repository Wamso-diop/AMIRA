"""S10 : performance avec le vrai modèle sur CPU (pytest -m model -s). Résultats notés dans docs/PERF.md."""
import statistics
import threading
import time
from pathlib import Path

import pytest

from amira import create_app
from amira.engine import NllbEngine
from conftest import DEV
from gold import rows, to_front

pytestmark = pytest.mark.model

# phrases françaises absentes du gold, sans chiffre (sinon la garde les refuse)
NEW = [f"{a} {b}." for a in ("Votre demande", "Ce service", "Votre carte", "Le paiement", "Votre virement")
       for b in ("est en cours de traitement", "a été refusé par la banque", "sera disponible demain", "nécessite une vérification")]


engine_calls = [0]  # segments réellement envoyés au modèle


@pytest.fixture(scope="module")
def engine():
    e = NllbEngine(str(Path(__file__).parents[1] / "models" / "nllb_ff"), {"fr": "fra_Latn", "en": "eng_Latn", "ff": "fuv_Latn"})
    e.load()
    real = e.translate

    def counting(texts, *args, **kwargs):
        out = real(texts, *args, **kwargs)
        engine_calls[0] += len(texts)
        return out

    e.translate = counting
    return e


def batch(offset=0):
    gold = [to_front(r["fr"]) for r in rows()[offset:offset + 20]]
    return {"requestId": "perf", "source": "fr", "target": "ff", "variety": "ngaoundere",
            "segments": [{"id": f"s{i}", "text": t, "placeholders": []} for i, t in enumerate(gold + NEW)]}


def timed(client, body):
    t0 = time.perf_counter()
    r = client.post("/v1/translate", json=body)
    assert r.status_code == 200
    return time.perf_counter() - t0, r.get_json()["segments"]


def test_lot_de_40_visites_successives(engine, db_path):
    """Même page (20 textes du gold + 20 inconnus) visitée plusieurs fois : latence, et segments traduits ou non."""
    client = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ENGINE": "nllb"}, engine=engine).test_client()
    print("\nvisite | durée | validated (mémoire) | machine (dont cache) | uncertain")
    covered, durations = [], []
    for visit in range(1, 8):
        calls_before = engine_calls[0]
        d, segs = timed(client, batch())
        st = [s["status"] for s in segs]
        new = engine_calls[0] - calls_before
        durations.append(d)
        covered.append(st[20:].count("machine"))
        print(f"{visit:6} | {d:5.2f} s | {st.count('validated'):19} | {st.count('machine'):3} ({st.count('machine') - new:2} du cache) "
              f"| {st.count('uncertain'):9}")
        assert st[:20].count("validated") == 20  # la mémoire ne dépend pas du moteur
        assert d < 8.0  # le front coupe à 8 s
    assert covered == sorted(covered) and covered[-1] > covered[0]  # la couverture ne fait que croître


def test_quatre_requetes_simultanees(engine, db_path):
    app = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ENGINE": "nllb"}, engine=engine)
    results = [None] * 4

    def go(i):
        results[i] = timed(app.test_client(), batch(offset=20 * i))

    threads = [threading.Thread(target=go, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    durations = [d for d, _ in results]
    machine = [sum(s["status"] == "machine" for s in segs) for _, segs in results]
    print(f"\n4 simultanées : durées {[round(d, 2) for d in durations]} s, segments machine {machine}")
    assert max(durations) < 8.0


def test_premier_appel_a_froid(db_path):
    e = NllbEngine(str(Path(__file__).parents[1] / "models" / "nllb_ff"), {"fr": "fra_Latn", "en": "eng_Latn", "ff": "fuv_Latn"})
    e.load()
    t0 = time.perf_counter()
    e.translate(["Votre demande est en cours."], "fr", "ff")
    cold = time.perf_counter() - t0
    t0 = time.perf_counter()
    e.translate(["Votre carte est bloquée."], "fr", "ff")
    warm = time.perf_counter() - t0
    print(f"\npremier appel {cold:.2f} s, suivant {warm:.2f} s")
