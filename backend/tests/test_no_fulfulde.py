"""P7 : aucun texte fulfulde écrit à la main dans le code ou les tests (ils viennent du CSV)."""
from pathlib import Path

from gold import rows
from tools.import_gold import refusal

ROOT = Path(__file__).parents[1]


def test_aucun_fulfulde_dans_le_code():
    words = {v.strip().lower() for r in rows() if refusal(r) != "nombre" for v in (r["ff"], r["ff_variants"]) if len(v.strip()) >= 4}
    files = [*ROOT.glob("amira/**/*.py"), *ROOT.glob("tools/*.py"), *ROOT.glob("tests/*.py")]
    found = [(f.name, w) for f in files for w in words if w in f.read_text(encoding="utf-8").lower()]
    assert len(words) > 90 and found == []
