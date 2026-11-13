"""Range les enregistrements du locuteur natif et les relie au CSV gold. Ne modifie ni le CSV ni le dossier source.

Usage (depuis backend/) : python -m tools.organize_audio <dossier des enregistrements bruts> languages/ff/gold.csv languages/ff/audio [--language ff]
Chaque fichier source porte comme nom le texte (dans la langue) qu'il dit. Il est copié dans <sortie>/<rubrique>/ sous un nom
ASCII qui commence par l'identifiant gold (g0077_…). Les phrases enregistrées en deux morceaux donnent _p1 et _p2.
<sortie>/index.csv dit pour chaque fichier : identifiants gold, partie, textes <langue>/fr/en, nom d'origine.
Rejouable : le dossier de sortie est reconstruit à chaque fois.
"""
import argparse
import csv
import os
import re
import shutil
import unicodedata
from pathlib import Path

from tools.import_gold import is_number

FOLDERS = {"glossaire": "mots", "ui": "interface", "message": "messages"}
ASCII = str.maketrans({"ɗ": "d", "ɓ": "b", "ƴ": "y", "ŋ": "ng", "Ɗ": "d", "Ɓ": "b", "Ƴ": "y", "Ŋ": "ng"})


def norm(text: str, wild: bool = False) -> str:
    """Forme de comparaison : minuscules, sans ponctuation ni montant ({V1}, {}, « 0 FCFA » : le natif les dit à sa façon).
    wild : chaque {V1} du gold reste un joker « § » (le natif peut dire un mot à la place du chiffre)."""
    t = unicodedata.normalize("NFC", text).lower().replace("’", "'")
    t = re.sub(r"\{v?\d*\}", " § " if wild else " ", t)
    t = re.sub(r"\d+|\bfcfa\b", " ", t)
    t = re.sub(r"[^\w'§]+|_", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.translate(ASCII).replace("{}", "v"))
    t = t.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60] or "audio"


def eat(form: list[str], said: list[str], whole: bool) -> bool:
    """Le texte dit correspond-il au gold, mot à mot ? « § » (un {V1}) absorbe 0 à 5 mots : le natif dit le nom ou le
    montant. whole : tout le gold doit être dit ; sinon le dit peut s'arrêter avant la fin (début de phrase coupée)."""
    if not said:
        return not whole or all(t == "§" for t in form)
    if not form:
        return False
    if form[0] == "§":
        # morceau coupé : le « § » ne peut pas absorber toute la fin du dit (il faut au moins un mot fixe du gold)
        return any(eat(form[1:], said[k:], whole) for k in range(min(5, len(said)) + 1) if whole or k < len(said))
    return form[0] == said[0] and eat(form[1:], said[1:], whole)


def match(name: str, rows: list[dict]) -> tuple[list[dict], str]:
    """(lignes gold, partie) : « entier », « p1 » (début de phrase), « p2 » (fin) ou « » si rien ne correspond."""
    said = norm(name).split()
    if not said:
        return [], ""
    # au moins deux mots fixes dans le gold, sinon « § § » absorberait n'importe quoi
    forms = lambda r: [f for f in r["_forms"] if sum(t != "§" for t in f) >= 2 or "§" not in f]
    full = [r for r in rows if any(eat(f, said, True) for f in forms(r))]
    if full:
        return full, "entier"
    # un morceau plus court que le gold ; bornes de mots
    for part, rev in (("p1", False), ("p2", True)):
        cut = (lambda t: t[::-1]) if rev else (lambda t: t)
        found = [r for r in rows if any(len(f) > len(said) and eat(cut(f), cut(said), False) for f in forms(r))]
        if found:
            return found, part
    return [], ""


def organize(source: Path, gold: Path, out: Path, lang: str = "ff") -> list[dict]:
    with gold.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    # mots des nombres : ceux du glossaire gold dont le français est un nombre (aucun texte de la langue écrit ici)
    numbers = {w for r in rows if is_number(r["fr"]) for w in norm(r[lang]).split()}
    for r in rows:
        forms = [v for v in [r[lang], *re.split(r"[|;]", r[f"{lang}_variants"])] if v.strip()]
        r["_forms"] = [norm(v, wild=True).split() for v in forms]

    if out.exists():
        shutil.rmtree(out)
    index, used = [], set()
    # sous-dossiers compris ; même texte enregistré plusieurs fois : le plus récent d'abord (réenregistrement)
    for src in sorted(source.rglob("*.m4a"), key=lambda p: (p.name.lower(), -p.stat().st_mtime, str(p))):
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
            lang: " || ".join(r[lang] for r in found), "fr": " || ".join(r["fr"] for r in found),
            "en": " || ".join(r["en"] for r in found), "nom_origine": src.relative_to(source).as_posix(),
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
    ap.add_argument("--language", default=os.environ.get("AMIRA_LANGUAGE", "ff"))
    args = ap.parse_args()
    index = organize(args.source, args.gold, args.out, args.language)
    rows = list(csv.DictReader(args.gold.open(encoding="utf-8-sig", newline="")))
    covered = {i for x in index for i in x["ids"].split("|") if i}
    missing = [r for r in rows if r["id"] not in covered]
    print(f"{len(index)} fichiers rangés dans {args.out}")
    for folder in sorted({x["rubrique"] for x in index}):
        print(f"  {folder:<11} {sum(x['rubrique'] == folder for x in index)}")
    print(f"lignes gold sans audio : {len(missing)} → {' '.join(r['id'] for r in missing)}")


if __name__ == "__main__":
    main()
