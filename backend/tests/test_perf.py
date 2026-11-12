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


@pytest.fixture(scope="module")
def engine():
    e = NllbEngine(str(Path(__file__).parents[1] / "models" / "nllb_ff"), {"fr": "fra_Latn", "en": "eng_Latn", "ff": "fuv_Latn"})
    e.load()
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


def test_lot_de_40(engine, db_path):
    client = create_app({**DEV, "AMIRA_DB_PATH": db_path, "AMIRA_ENGINE": "nllb"}, engine=engine).test_client()
    runs = [timed(client, batch()) for _ in range(5)]
    durations = sorted(d for d, _ in runs)
    statuses = [[s["status"] for s in segs] for _, segs in runs]
    median, p95 = statistics.median(durations), durations[-1]  # 5 essais : p95 = le plus lent
    print(f"\nlot de 40 : médiane {median:.2f} s, p95 {p95:.2f} s, essais {[round(d, 2) for d in durations]}")
    for st in statuses:
        print("  validated", st.count("validated"), "machine", st.count("machine"), "uncertain", st.count("uncertain"))
    assert p95 < 8.0  # le front coupe à 8 s
    assert all(st[:20].count("validated") == 20 for st in statuses)  # la mémoire ne dépend pas du moteur


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
