"""Import idempotent de la mémoire validée (CSV gold) dans SQLite. Ne modifie jamais le CSV.

Usage (depuis backend/) : python -m tools.import_gold data/gold_fulfulde.csv --validator natif-1 [--db data/amira.sqlite3]
Chaque ligne donne fr>ff, en>ff, ff>fr et ff>en (variantes comprises). {V1}→{N0}, {V2}→{N1}…
Rejouer l'import met la base à jour : entrées changées réécrites, entrées disparues du CSV supprimées.
"""
import argparse
import csv
import os
import re

from amira import db
from amira.guard import check
from amira.markers import MARKER_RE, canonicalize, markers_ok, restore

FF_VARIETY = "ngaoundere"  # le CSV n'a pas de colonne variété : fulfulde de l'Adamaoua
PRIORITY = {"ui": 0, "message": 0, "glossaire": 1}  # en cas de conflit, ui et message passent devant le glossaire
DIRECTIONS = [("fr", "ff"), ("en", "ff"), ("ff", "fr"), ("ff", "en")]


def to_front(text: str) -> str:
    return re.sub(r"\{V(\d+)\}", lambda m: f"{{N{int(m.group(1)) - 1}}}", text.strip())


def variants(cell: str) -> list[str]:
    return [v.strip() for v in re.split(r"[|;]", cell) if v.strip()]


def refusal(row: dict) -> str | None:
    texts = {c: to_front(row[c]) for c in ("fr", "en", "ff")}
    if not (markers_ok(texts["ff"], texts["fr"]) and markers_ok(texts["ff"], texts["en"])):
        return "marqueurs"
    if row.get("n_markers", "").strip() and int(row["n_markers"]) != len(MARKER_RE.findall(texts["ff"])):
        return "n_markers"
    if not all(check(to_front(t)) for c in ("fr", "en", "ff", "fr_variants", "en_variants", "ff_variants") for t in [row[c]]):
        return "garde"
    return None


def import_gold(conn, path, validator: str) -> dict:
    if not validator.strip():
        raise ValueError("nom du natif obligatoire (--validator)")
    with open(path, encoding="utf-8-sig", newline="") as f:
        data = list(csv.DictReader(f))

    refused, conflicts, chosen = [], [], {}
    for row in data:
        reason = refusal(row)
        if reason:
            refused.append({"id": row["id"], "reason": reason})
            continue
        for src, tgt in DIRECTIONS:
            target = to_front(row[tgt])
            if not target:
                continue
            for source in [to_front(row[src])] + [to_front(v) for v in variants(row[f"{src}_variants"])]:
                if not source:
                    continue
                canon, table = canonicalize(source)
                # la traduction suit la numérotation canonique de la source
                text = restore(target, {o: c for c, o in table.items()})
                variety = FF_VARIETY if tgt == "ff" else ""
                k = (src, tgt, variety, db.memory_key(source))
                entry = {"source_masked": canon, "text": text, "kind": row["kind"], "ref": "gold:" + row["id"]}
                old = chosen.get(k)
                if old and old["text"] != text:
                    keep_new = PRIORITY.get(row["kind"], 1) < PRIORITY.get(old["kind"], 1)
                    kept, dropped = (entry, old) if keep_new else (old, entry)
                    conflicts.append({"direction": f"{src}>{tgt}", "kept": kept["ref"][5:], "dropped": dropped["ref"][5:]})
                    chosen[k] = kept
                elif not old:
                    chosen[k] = entry

    stamp = db.now()
    with conn:
        for (src, tgt, variety, key), e in chosen.items():
            conn.execute(
                "INSERT INTO translations (source, target, variety, key, source_masked, text, kind, validated_by, ref, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (source, target, variety, key) DO UPDATE SET source_masked = excluded.source_masked, "
                "text = excluded.text, kind = excluded.kind, validated_by = excluded.validated_by, ref = excluded.ref, "
                "updated_at = excluded.updated_at "
                "WHERE translations.text <> excluded.text OR translations.kind <> excluded.kind "
                "OR translations.validated_by <> excluded.validated_by OR translations.ref <> excluded.ref "
                "OR translations.source_masked <> excluded.source_masked",
                (src, tgt, variety, key, e["source_masked"], e["text"], e["kind"], validator, e["ref"], stamp),
            )
        # entrées gold disparues du CSV (source corrigée, ligne retirée)
        current = set(chosen)
        for r in conn.execute("SELECT source, target, variety, key FROM translations WHERE ref LIKE 'gold:%'").fetchall():
            if tuple(r) not in current:
                conn.execute("DELETE FROM translations WHERE source = ? AND target = ? AND variety = ? AND key = ?", tuple(r))
        db.audit(conn, validator, "import_gold", f"{len(chosen)} entrées")
    return {"rows": len(data), "entries": len(chosen), "refused": refused, "conflicts": conflicts}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv")
    ap.add_argument("--validator", required=True, help="nom du locuteur natif qui a relu le fichier")
    ap.add_argument("--db", default=os.environ.get("AMIRA_DB_PATH", "data/amira.sqlite3"))
    args = ap.parse_args()
    report = import_gold(db.connect(args.db), args.csv, args.validator)
    print(f"lignes lues : {report['rows']}, entrées en mémoire : {report['entries']}")
    print(f"lignes refusées : {len(report['refused'])}")
    for r in report["refused"]:
        print(f"  {r['id']} : {r['reason']}")
    print(f"conflits : {len(report['conflicts'])}")
    for c in report["conflicts"]:
        print(f"  {c['direction']} : {c['kept']} gardée, {c['dropped']} écartée")


if __name__ == "__main__":
    main()
