"""Régénère tests/fixtures/regression_gold.json : requêtes servies par la mémoire validée + réponse complète.

À lancer UNE fois, avant de toucher au moteur : « python tests/make_regression_gold.py ».
Ces réponses ne dépendent pas du moteur ; le test les compare octet pour octet (sauf latencyMs).
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1]))

from amira import create_app, db  # noqa: E402
from gold import GOLD, rows, to_front  # noqa: E402
from tools.import_gold import import_gold  # noqa: E402

OUT = Path(__file__).parent / "fixtures" / "regression_gold.json"
DEV = {"AMIRA_ENV": "development", "AMIRA_ENGINE": "memory"}
DIRS = [("fr", "ff"), ("en", "ff"), ("ff", "fr"), ("ff", "en")]


def cases() -> list[dict]:
    rs = rows()
    out = []
    for i, r in enumerate(rs):
        src, tgt = DIRS[i % 4]
        if r[src] and r[tgt]:
            out.append({"requestId": f"9f1c2a7b3d4e{i:04x}", "source": src, "target": tgt, "variety": "ngaoundere",
                        "segments": [{"id": "s1", "text": to_front(r[src]), "placeholders": []}]})
    return out


def replay(app, reqs: list[dict]) -> list[dict]:
    res = []
    for q in reqs:
        body = app.test_client().post("/v1/translate", json=q).get_json()
        body.pop("latencyMs", None)
        res.append(body)
    return res


def memory_app(tmp: str):
    path = str(Path(tmp) / "amira.sqlite3")
    conn = db.connect(path)
    import_gold(conn, GOLD, "natif-1")
    conn.close()
    return create_app({**DEV, "AMIRA_DB_PATH": path}, engine=None)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        reqs = cases()
        data = [{"request": q, "response": r} for q, r in zip(reqs, replay(memory_app(tmp), reqs))]
    # on ne garde que ce que la mémoire sert vraiment : 8 avec marqueurs, 12 sans
    served = [d for d in data if d["response"]["segments"][0]["origin"] == "memory"]
    marked = [d for d in served if "{N" in d["request"]["segments"][0]["text"]][:8]
    plain = [d for d in served if "{N" not in d["request"]["segments"][0]["text"]][::6][:12]
    data = marked + plain
    assert len(data) == 20 and all(d["response"]["segments"][0]["status"] == "validated" for d in data)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(data), "cas écrits dans", OUT)
