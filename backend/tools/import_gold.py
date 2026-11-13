"""Import idempotent de la mémoire validée (CSV gold) dans SQLite. Ne modifie jamais le CSV.

Usage (depuis backend/) : python -m tools.import_gold languages/ff/gold.csv --validator natif-1 [--language ff] [--db data/amira.sqlite3]
Chaque ligne donne fr>xx, en>xx, xx>fr et xx>en (variantes comprises), xx étant la langue (colonne du CSV du même nom). {V1}→{N0}, {V2}→{N1}…
Rejouer l'import met la base à jour : entrées changées réécrites, entrées disparues du CSV supprimées.
"""
import argparse
import csv
import os
import re

from amira import db
from amira.config import load_language
from amira.guard import check
from amira.markers import MARKER_RE, canonicalize, markers_ok, restore

DEFAULT_VARIETY = "ngaoundere"  # le CSV n'a pas de colonne variété : celle de language.json (fulfulde de l'Adamaoua par défaut)
PRIORITY = {"ui": 0, "message": 0, "glossaire": 1}  # en cas de conflit, ui et message passent devant le glossaire
PIVOTS = ("fr", "en")  # langues de l'interface bancaire : jamais fr↔en
# Un nombre ne se traduit jamais (chiffres masqués par le front, garde côté serveur) : pas même écrit en lettres.
NUMBER_WORDS = set("""un une deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize vingt
trente quarante cinquante soixante cent cents mille million millions milliard milliards et
one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen
nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million billion and""".split())


def to_front(text: str) -> str:
    return re.sub(r"\{V(\d+)\}", lambda m: f"{{N{int(m.group(1)) - 1}}}", text.strip())


def variants(cell: str) -> list[str]:
    return [v.strip() for v in re.split(r"[|;]", cell) if v.strip()]


def is_number(text: str) -> bool:
    words = re.findall(r"[^\W\d_]+", text.lower())
    return bool(set(words) - {"et", "and"}) and all(w in NUMBER_WORDS for w in words)


def refusal(row: dict, lang: str = "ff") -> str | None:
    if any(is_number(row[c]) for c in ("fr", "en")):
        return "nombre"
    # une ligne exportée de l'admin n'a que deux colonnes remplies : on compare celles qui existent
    texts = [to_front(row[c]) for c in (lang, "fr", "en") if row[c].strip()]
    if not all(markers_ok(texts[0], t) for t in texts[1:]):
        return "marqueurs"
    if row.get("n_markers", "").strip() and int(row["n_markers"]) != len(MARKER_RE.findall(texts[0] if texts else "")):
        return "n_markers"
    if not all(check(to_front(t)) for c in ("fr", "en", lang, "fr_variants", "en_variants", f"{lang}_variants") for t in [row[c]]):
        return "garde"
    return None


def import_gold(conn, path, validator: str, lang: str = "ff", variety: str = DEFAULT_VARIETY) -> dict:
    if not validator.strip():
        raise ValueError("nom du natif obligatoire (--validator)")
    with open(path, encoding="utf-8-sig", newline="") as f:
        data = list(csv.DictReader(f))

    refused, conflicts, chosen = [], [], {}
    for row in data:
        reason = refusal(row, lang)
        if reason:
            refused.append({"id": row["id"], "reason": reason})
            continue
        for src, tgt in [(p, lang) for p in PIVOTS] + [(lang, p) for p in PIVOTS]:
            target = to_front(row[tgt])
            if not target:
                continue
            for source in [to_front(row[src])] + [to_front(v) for v in variants(row[f"{src}_variants"])]:
                if not source:
                    continue
                canon, table = canonicalize(source)
                # la traduction suit la numérotation canonique de la source
                text = restore(target, {o: c for c, o in table.items()})
                vty = variety if tgt == lang else ""
                k = (src, tgt, vty, db.memory_key(source))
                entry = {"source_masked": canon, "text": text, "kind": row["kind"], "ref": "gold:" + row["id"]}
                old = chosen.get(k)
                if old and old["text"] != text:
                    keep_new = PRIORITY.get(row["kind"], 1) < PRIORITY.get(old["kind"], 1)
                    kept, dropped = (entry, old) if keep_new else (old, entry)
                    conflicts.append({"direction": f"{src}>{tgt}", "kept": kept["ref"][5:], "dropped": dropped["ref"][5:]})
                    chosen[k] = kept
                elif not old:
                    chosen[k] = entry

    # l'import ne touche jamais une entrée créée par l'admin : il signale la différence sans trancher
    admin = {tuple(r[:4]): r[4] for r in conn.execute(
        "SELECT source, target, variety, key, text FROM translations WHERE ref = 'admin'").fetchall()}
    for k, e in list(chosen.items()):
        if k in admin:
            if admin[k] != e["text"]:
                conflicts.append({"direction": f"{k[0]}>{k[1]}", "kept": "admin", "dropped": e["ref"][5:], "decided": False})
            del chosen[k]

    stamp = db.now()
    with conn:
        for (src, tgt, variety, key), e in chosen.items():
            conn.execute(
                "INSERT INTO translations (source, target, variety, key, source_masked, text, kind, validated_by, ref, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (source, target, variety, key) DO UPDATE SET source_masked = excluded.source_masked, "
                "text = excluded.text, kind = excluded.kind, validated_by = excluded.validated_by, ref = excluded.ref, "
                "updated_at = excluded.updated_at "
                # protection atomique : même une écriture admin arrivée pendant l'import n'est jamais écrasée
                "WHERE translations.ref <> 'admin' AND (translations.text <> excluded.text OR translations.kind <> excluded.kind "
                "OR translations.validated_by <> excluded.validated_by OR translations.ref <> excluded.ref "
                "OR translations.source_masked <> excluded.source_masked)",
                (src, tgt, variety, key, e["source_masked"], e["text"], e["kind"], validator, e["ref"], stamp),
            )
        # entrées gold disparues du CSV (source corrigée, ligne retirée)
        current = set(chosen)
        # seulement les sens de cette langue : le gold d'une autre langue de la même base n'est pas touché
        for r in conn.execute("SELECT source, target, variety, key FROM translations WHERE ref LIKE 'gold:%' "
                              "AND (source = ? OR target = ?)", (lang, lang)).fetchall():
            if tuple(r) not in current:
                conn.execute("DELETE FROM translations WHERE source = ? AND target = ? AND variety = ? AND key = ?", tuple(r))
        db.audit(conn, validator, "import_gold", f"{len(chosen)} entrées")
    return {"rows": len(data), "entries": len(chosen), "refused": refused, "conflicts": conflicts}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv")
    ap.add_argument("--validator", required=True, help="nom du locuteur natif qui a relu le fichier")
    ap.add_argument("--db", default=os.environ.get("AMIRA_DB_PATH", "data/amira.sqlite3"))
    ap.add_argument("--language", default=os.environ.get("AMIRA_LANGUAGE", "ff"), help="code de la langue (dossier languages/<code>)")
    args = ap.parse_args()
    variety = load_language(args.language)["varieties"][0]
    report = import_gold(db.connect(args.db), args.csv, args.validator, args.language, variety)
    print(f"lignes lues : {report['rows']}, entrées en mémoire : {report['entries']}")
    print(f"lignes refusées : {len(report['refused'])}")
    for r in report["refused"]:
        print(f"  {r['id']} : {r['reason']}")
    print(f"conflits : {len(report['conflicts'])}")
    for c in report["conflicts"]:
        decided = "" if c.get("decided", True) else " (non tranché : à régler avec le natif)"
        print(f"  {c['direction']} : {c['kept']} gardée, {c['dropped']} écartée{decided}")


if __name__ == "__main__":
    main()
