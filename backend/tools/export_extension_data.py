"""Exporte la mémoire validée et les voix des natifs DANS l'extension : elle agit alors seule, sans serveur.

Usage (depuis backend/) : python -m tools.export_extension_data [--language ff] [--front ../front] [--audio-budget-mb 7.2]
Écrit, dans le dossier du front :
  src/data/memory.json            les traductions validées (clés de mémoire, par sens et variété)
  src/data/audio.json             clé de segment → fichier audio, pour la langue
  public/audio/<empreinte>.m4a    les voix (dédoublonnées), dans la limite du budget
  tests/fixtures/embedded_vectors.json   requêtes et réponses du VRAI serveur, pour vérifier que la version embarquée est identique

Rien n'est inventé : tout vient de languages/<code>/gold.csv et de languages/<code>/audio (relus par le locuteur natif).
Le budget fixe le poids des voix : l'extension doit tenir dans 10 Mo une fois compressée.
"""
import argparse
import csv
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from amira import db
from amira.config import LANGUAGES_DIR, load_language
from amira.services.translator import from_memory
from amira.services.voice import audio_key
from tools.import_audio import import_audio
from tools.import_gold import import_gold, refusal, to_front, variants

KIND_ORDER = {"message": 0, "ui": 1, "glossaire": 2}  # les messages (erreurs, avertissements) d'abord : ce sont eux que l'on lit tout seul


def export_memory(conn) -> dict:
    tables: dict[str, dict[str, str]] = {}
    for r in conn.execute("SELECT source, target, variety, key, text FROM translations ORDER BY source, target, variety, key"):
        tables.setdefault(f"{r['source']}>{r['target']}|{r['variety']}", {})[r["key"]] = r["text"]
    return tables


def export_audio(conn, rows: list[dict], lang: str, out_dir: Path, budget: int) -> tuple[dict[str, str], dict]:
    """Choisit les voix par priorité (messages, libellés, mots) jusqu'au budget. Renvoie (clé → fichier, bilan)."""
    recs = {r["segment_key"]: Path(r["path"]) for r in conn.execute("SELECT segment_key, path FROM recordings WHERE language = ?", (lang,))}
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.m4a"):  # sortie reconstruite à chaque fois
        old.unlink()
    index: dict[str, str] = {}
    by_hash: dict[str, str] = {}
    total = skipped = 0
    for row in sorted(rows, key=lambda r: (KIND_ORDER.get(r["kind"], 9), r["id"])):
        keys = {audio_key(to_front(t)) for c in ("fr", "en") for t in [row[c], *variants(row[f"{c}_variants"])] if t.strip()}
        for k in sorted(keys):
            path = recs.get(k)
            if path is None or k in index:
                continue
            data = path.read_bytes()
            h = hashlib.sha256(data).hexdigest()[:12]
            if h not in by_hash:
                if total + len(data) > budget:
                    skipped += 1
                    continue
                (out_dir / f"{h}.m4a").write_bytes(data)
                by_hash[h] = f"{h}.m4a"
                total += len(data)
            index[k] = by_hash[h]
    return index, {"files": len(by_hash), "bytes": total, "keys": len(index), "keys_sans_voix_faute_de_place": skipped}


def vectors(conn, rows: list[dict], lang: str, variety: str) -> list[dict]:
    """Requêtes variées (casse, ponctuation, espaces, apostrophes, fin de segment, marqueurs) et réponse du VRAI serveur."""
    texts: list[tuple[str, str, str]] = []  # (source, target, texte)
    for r in rows:
        for c in ("fr", "en", lang):
            for t in [r[c], *variants(r[f"{c}_variants"])]:
                if not t.strip():
                    continue
                t = to_front(t)
                src, tgt = (c, lang) if c != lang else (lang, "fr")
                texts += [(src, tgt, t), (src, tgt, t.upper()), (src, tgt, "  " + t.rstrip(".!?:;, ") + " ! "),
                          (src, tgt, t.replace("'", "’")), (src, tgt, t.replace(" :", ":"))]
                if c == "fr":
                    texts += [("fr", lang, t.rstrip(".") + " : CM {N0}"), ("fr", lang, t.replace("{N0}", "{N3}")),
                              ("en", lang, t), ("fr", "en", t)]  # sens non autorisé fr>en : la mémoire ne le contient pas
    texts += [("fr", lang, "Un texte que la mémoire ne connaît pas"), ("fr", lang, "{N0} {N1}"), ("fr", lang, ""), ("en", lang, "Unknown sentence {N0}")]
    seen, out = set(), []
    for src, tgt, text in texts:
        if (src, tgt, text) in seen:
            continue
        seen.add((src, tgt, text))
        v = variety if tgt == lang else ""
        out.append({"source": src, "target": tgt, "variety": v, "text": text, "expected": from_memory(conn, text, src, tgt, v)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--language", default="ff")
    ap.add_argument("--front", type=Path, default=Path("../front"))
    ap.add_argument("--audio-budget-mb", type=float, default=8.0)
    args = ap.parse_args()
    lang = args.language
    info = load_language(lang)
    variety = info["varieties"][0]
    gold = LANGUAGES_DIR / lang / "gold.csv"
    audio = LANGUAGES_DIR / lang / "audio"
    with tempfile.TemporaryDirectory() as tmp:
        conn = db.connect(str(Path(tmp) / "export.sqlite3"))
        import_gold(conn, gold, "natif-1", lang, variety)
        rows = [r for r in csv.DictReader(gold.open(encoding="utf-8-sig", newline="")) if not refusal(r, lang)]
        tables = export_memory(conn)
        index, bilan = {}, {"files": 0, "bytes": 0, "keys": 0, "keys_sans_voix_faute_de_place": 0}
        if (audio / "index.csv").exists():
            import_audio(conn, audio, gold, Path(tmp) / "rec", "natif-1", lang)
            index, bilan = export_audio(conn, rows, lang, args.front / "public" / "audio", int(args.audio_budget_mb * 1_000_000))
        vec = vectors(conn, rows, lang, variety)
        conn.close()
    data = args.front / "src" / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "memory.json").write_text(json.dumps({"language": lang, "variety": variety, "tables": tables}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    (data / "audio.json").write_text(json.dumps({"language": lang, "keys": index}, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    fx = args.front / "tests" / "fixtures"
    fx.mkdir(parents=True, exist_ok=True)
    (fx / "embedded_vectors.json").write_text(json.dumps(vec, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    n = sum(len(t) for t in tables.values())
    print(f"mémoire : {n} entrées dans {len(tables)} sens ; voix : {bilan['keys']} passages, {bilan['files']} fichiers, "
          f"{bilan['bytes'] / 1e6:.2f} Mo ({bilan['keys_sans_voix_faute_de_place']} sans voix faute de place) ; vecteurs de test : {len(vec)}")


if __name__ == "__main__":
    main()
