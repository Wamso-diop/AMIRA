"""Lecture du CSV gold pour les tests (P7 : aucun fulfulde écrit à la main dans les tests)."""
import csv
import re
from pathlib import Path

GOLD = Path(__file__).parents[1] / "languages" / "ff" / "gold.csv"


def rows() -> list[dict]:
    with GOLD.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def to_front(text: str) -> str:
    """{V1} → {N0}, {V2} → {N1}… (format du front)."""
    return re.sub(r"\{V(\d+)\}", lambda m: f"{{N{int(m.group(1)) - 1}}}", text)
