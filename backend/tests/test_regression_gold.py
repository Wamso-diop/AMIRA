"""Les réponses servies par la mémoire validée ne dépendent pas du moteur : elles ne doivent jamais changer."""
import json
from pathlib import Path

import pytest

from make_regression_gold import replay

CASES = json.loads((Path(__file__).parent / "fixtures" / "regression_gold.json").read_text(encoding="utf-8"))


def test_la_fixture_couvre_vingt_cas_dont_des_marqueurs():
    assert len(CASES) == 20
    assert sum("{N" in c["request"]["segments"][0]["text"] for c in CASES) >= 8


def sans_version(body: dict) -> dict:
    return {k: v for k, v in body.items() if k != "engineVersion"}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["request"]["requestId"])
def test_reponse_identique_hors_engine_version(gold_app, case):
    """La fixture date d'avant le changement d'engineVersion : tout le reste de la réponse doit être identique."""
    (got,) = replay(gold_app, [case["request"]])
    assert sans_version(got) == sans_version(case["response"])


def test_engine_version_change_seule():
    old = {c["response"]["engineVersion"] for c in CASES}
    assert old == {"amira-nllb-ff-stage2"}  # trace de l'état d'avant


def test_engine_version_actuelle(gold_app):
    (got,) = replay(gold_app, [CASES[0]["request"]])
    assert got["engineVersion"] == "amira-m2m100-ff-stage2"
