"""Crée le squelette d'une nouvelle langue : languages/<code>/ (fiche, mémoire vide, audio, phrases de contrôle).

Usage (depuis backend/) : python -m tools.new_language <code> [--variety v1,v2]
Exemple : python -m tools.new_language bbj --variety ghomala
Aucun mot de la langue n'est écrit : la mémoire est vide, à remplir par un locuteur natif (voir languages/README.md).
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

from amira.config import LANGUAGES_DIR

COLUMNS = ["id", "kind", "section", "page", "fr", "en", "{l}", "fr_variants", "en_variants", "{l}_variants", "notes", "observed", "n_markers"]
CONTROL = ["Votre carte a été bloquée par mesure de sécurité.", "Veuillez patienter pendant le traitement de votre demande.",
           "Ne partagez jamais votre code secret avec un inconnu.", "Votre demande de prêt a été acceptée."]


def create(code: str, varieties: list[str], root: Path = LANGUAGES_DIR) -> Path:
    if not re.fullmatch(r"[a-z]{2,3}", code) or code in ("fr", "en"):
        raise ValueError("code : 2 ou 3 lettres minuscules (ISO 639), différent de fr et en")
    folder = root / code
    if folder.exists():
        raise FileExistsError(f"{folder} existe déjà")
    (folder / "audio").mkdir(parents=True)
    (folder / "audio" / ".gitkeep").touch()
    info = {"code": code, "name": code, "varieties": varieties or ["standard"],
            "model_dir": f"models/m2m_{code}", "engine_version": f"amira-m2m100-{code}-v1"}
    (folder / "language.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (folder / "gold.csv").open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow([c.format(l=code) for c in COLUMNS])
    (folder / "check_model.json").write_text(json.dumps({"control": {"source": CONTROL[0]}, "sentences": CONTROL},
                                                        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return folder


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("code")
    ap.add_argument("--variety", default="", help="variétés, séparées par des virgules (la première est celle par défaut)")
    args = ap.parse_args()
    try:
        folder = create(args.code, [v.strip() for v in args.variety.split(",") if v.strip()])
    except (ValueError, FileExistsError) as e:
        sys.exit(str(e))
    print(f"créé : {folder}\nsuite : languages/README.md (nom, mémoire validée, modèle, interface)")


if __name__ == "__main__":
    main()
