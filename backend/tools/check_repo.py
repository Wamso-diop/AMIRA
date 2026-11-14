"""Échoue si le dépôt contient un poids de modèle ou un gros fichier (index git compris).

Usage : python tools/check_repo.py   (branché sur le hook pre-commit et sur la liste /ship)
"""
import subprocess
import sys

MAX = 50 * 1024 * 1024
WEIGHTS = (".safetensors", ".bin", ".pt", ".gguf")


def git(*args: str, stdin: str | None = None) -> str:
    return subprocess.run(["git", *args], input=stdin, capture_output=True, text=True, check=True).stdout


def problems() -> list[str]:
    root = git("rev-parse", "--show-toplevel").strip()
    # « ls-files -s » = fichiers suivis ET indexés (y compris ceux qu'on vient de « git add »)
    entries = [line.split(None, 3) for line in git("-C", root, "ls-files", "-s").splitlines()]
    sizes = git("-C", root, "cat-file", "--batch-check=%(objectsize)", stdin="".join(e[1] + "\n" for e in entries)).split()
    out = []
    for (_mode, _sha, _stage, path), size in zip(entries, map(int, sizes)):
        if "models" in path.split("/")[:-1] or path.endswith(WEIGHTS):
            out.append(f"poids de modèle indexé : {path}")
        if size > MAX:
            out.append(f"fichier de {size / 2**20:.0f} MiB (> 50 MiB) : {path}")
    return out


if __name__ == "__main__":
    bad = problems()
    print("\n".join(bad) if bad else "dépôt sain : aucun poids, aucun fichier > 50 MiB")
    sys.exit(1 if bad else 0)
