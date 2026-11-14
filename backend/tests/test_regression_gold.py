"""Les réponses servies par la mémoire validée ne dépendent pas du moteur : elles ne doivent jamais changer."""
import json
from pathlib import Path

import pytest

from make_regression_gold import replay

CASES = json.loads((Path(__file__).parent / "fixtures" / "regression_gold.json").read_text(encoding="utf-8"))


def test_la_fixture_couvre_vingt_cas_dont_des_marqueurs():
    assert len(CASES) == 20
    assert sum("{N" in c["request"]["segments"][0]["text"] for c in CASES) >= 8


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["request"]["requestId"])
def test_reponse_identique(gold_app, case):
    assert replay(gold_app, [case["request"]]) == [case["response"]]
