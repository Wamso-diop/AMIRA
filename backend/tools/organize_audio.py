"""Range les enregistrements du locuteur natif et les relie au CSV gold. Ne modifie ni le CSV ni le dossier source.

Usage (depuis backend/) : python -m tools.organize_audio "data/Voice recording" data/gold_fulfulde.csv data/audio
Chaque fichier source porte comme nom le texte fulfulde qu'il dit. Il est copié dans <sortie>/<rubrique>/ sous un nom
ASCII qui commence par l'identifiant gold (g0077_…). Les phrases enregistrées en deux morceaux donnent _p1 et _p2.
<sortie>/index.csv dit pour chaque fichier : identifiants gold, partie, textes ff/fr/en, nom d'origine.
Rejouable : le dossier de sortie est reconstruit à chaque fois.
"""
import argparse
import csv
import re
import shutil
import unicodedata
from pathlib import Path

from tools.import_gold import is_number

FOLDERS = {"glossaire": "mots", "ui": "interface", "message": "messages"}
ASCII = str.maketrans({"ɗ": "d", "ɓ": "b", "ƴ": "y", "ŋ": "ng", "Ɗ": "d", "Ɓ": "b", "Ƴ": "y", "Ŋ": "ng"})


def norm(text: str) -> str:
    """Forme de comparaison : minuscules, sans ponctuation ni montant ({V1}, {}, « 0 FCFA » : le natif les dit à sa façon)."""
    t = unicodedata.normalize("NFC", text).lower().replace("’", "'")
    t = re.sub(r"\{v?\d*\}|\d+|\bfcfa\b", " ", t)
    t = re.sub(r"[^\w']+|_", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.translate(ASCII).replace("{}", "v"))
    t = t.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60] or "audio"


def match(name: str, rows: list[dict]) -> tuple[list[dict], str]:
    """(lignes gold, partie) : « entier », « p1 » (début de phrase), « p2 » (fin) ou « » si rien ne correspond."""
    n = norm(name)
    if not n:
        return [], ""
    full = [r for r in rows if n in r["_forms"]]
    if full:
        return full, "entier"
    for part, test in (("p1", str.startswith), ("p2", str.endswith)):
        # bornes de mots : un mot court ne doit pas trouver un mot plus long qui commence pareil
        found = [r for r in rows if any(test(f" {f} ", f" {n} ") for f in r["_forms"] if len(f) > len(n))]
        if found:
            return found, part
    return [], ""


def organize(source: Path, gold: Path, out: Path) -> list[dict]:
    with gold.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    # mots des nombres : ceux du glossaire gold dont le français est un nombre (aucun fulfulde écrit ici)
    numbers = {w for r in rows if is_number(r["fr"]) for w in norm(r["ff"]).split()}
    for r in rows:
        r["_forms"] = {norm(v) for v in [r["ff"], *re.split(r"[|;]", r["ff_variants"])] if v.strip()}

    if out.exists():
        shutil.rmtree(out)
    index, used = [], set()
    for src in sorted(source.glob("*.m4a"), key=lambda p: p.name.lower()):
        stem = unicodedata.normalize("NFC", src.stem)
        take = re.search(r"-(\d+)$", stem)  # « …-1 » : deuxième prise du même texte
        text = re.sub(r"-\d+$", "", stem).strip()
        found, part = match(text, rows)
        ids = sorted({r["id"] for r in found})
        kinds = {r["kind"] for r in found}
        if found:  # plusieurs lignes : morceau commun à plusieurs phrases, ou mot présent dans deux rubriques
            prefix = ids[0] if len(ids) == 1 else "commun"
            folder = FOLDERS.get(kinds.pop(), "autres") if len(kinds) == 1 else "mots" if part == "entier" else "messages"
        else:
            words = norm(text).split()
            is_num = words and 2 * sum(w in numbers for w in words) >= len(words)
            folder, prefix = ("nombres" if is_num else "a_verifier"), "hors-gold"
        base = "_".join(x for x in [prefix, part if part in ("p1", "p2") else "", slug(text)] if x)
        n = int(take.group(1)) + 1 if take else 1
        name = f"{base}_prise{n}" if take else base
        while name in used:  # même texte enregistré plusieurs fois (« …-1 », « … » final)
            n += 1
            name = f"{base}_prise{n}"
        used.add(name)
        dest = out / folder / f"{name}.m4a"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        index.append({
            "fichier": dest.relative_to(out).as_posix(), "ids": "|".join(ids), "partie": part or "?",
            "rubrique": folder, "texte_audio": text,
            "ff": " || ".join(r["ff"] for r in found), "fr": " || ".join(r["fr"] for r in found),
            "en": " || ".join(r["en"] for r in found), "nom_origine": src.name,
        })

    with (out / "index.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(index[0]))
        w.writeheader()
        w.writerows(sorted(index, key=lambda x: (x["rubrique"], x["fichier"])))

    return index


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("gold", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    index = organize(args.source, args.gold, args.out)
    rows = list(csv.DictReader(args.gold.open(encoding="utf-8-sig", newline="")))
    covered = {i for x in index for i in x["ids"].split("|") if i}
    missing = [r for r in rows if r["id"] not in covered]
    print(f"{len(index)} fichiers rangés dans {args.out}")
    for folder in sorted({x["rubrique"] for x in index}):
        print(f"  {folder:<11} {sum(x['rubrique'] == folder for x in index)}")
    print(f"lignes gold sans audio : {len(missing)} → {' '.join(r['id'] for r in missing)}")


if __name__ == "__main__":
    main()
