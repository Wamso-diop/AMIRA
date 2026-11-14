"""Lance Amira en démonstration : une commande, aucune configuration.   python demo.py [--language ff] [--port 5000]

- crée .venv et installe Flask au besoin (Python 3.10+ ; seul Flask est requis sans le modèle) ;
- sert la mémoire validée (languages/<code>/gold.csv) ; si le modèle M2M100 est dans models/m2m_<code>/, il complète la mémoire ;
- écoute sur 127.0.0.1 seulement. Pour la production : gunicorn (voir docs/EXPLOITATION.md).
"""
import argparse
import importlib.util
import os
import subprocess
import sys
import venv
from pathlib import Path

HERE = Path(__file__).parent
VENV = Path(os.environ.get("AMIRA_DEMO_VENV", HERE / ".venv"))
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_env() -> None:
    """Relance ce script dans le venv, après l'avoir créé et équipé de Flask s'il le faut."""
    if Path(sys.prefix).resolve() == VENV.resolve():
        return
    if not PY.exists():
        print("Première utilisation : création de l'environnement Python…")
        venv.create(VENV, with_pip=True)
    if subprocess.run([str(PY), "-c", "import flask, dotenv"], capture_output=True).returncode:
        print("Installation de Flask (une seule fois)…")
        subprocess.run([str(PY), "-m", "pip", "install", "-q", "Flask==3.1.3", "python-dotenv==1.2.4"], check=True)
    sys.exit(subprocess.call([str(PY), __file__, *sys.argv[1:]]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--language", default="ff")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args()
    ensure_env()
    os.chdir(HERE)
    sys.path.insert(0, str(HERE))
    from amira import config, create_app, db

    model = HERE / config.load_language(args.language)["model_dir"]
    # le modèle exige aussi torch, transformers et sentencepiece (requirements.txt) ; sinon, mémoire validée seule
    has_ml = all(importlib.util.find_spec(m) for m in ("torch", "transformers", "sentencepiece"))
    engine = "m2m100" if has_ml and (model / "model.safetensors").exists() else "memory"
    env = {**os.environ, "AMIRA_ENV": "development", "AMIRA_LANGUAGE": args.language, "AMIRA_ENGINE": engine,
           "AMIRA_DB_PATH": "data/demo.sqlite3", "AMIRA_GOLD_VALIDATOR": "natif-1"}
    app = create_app(env)
    conn = db.connect(app.config["DB_PATH"])
    audio = HERE / "languages" / args.language / "audio"
    if (audio / "index.csv").exists():  # voix des natifs : le serveur ne sert que celles déclarées en base (import rejouable)
        from tools.import_audio import import_audio
        r = import_audio(conn, audio, Path(app.config["GOLD_PATH"]), Path(app.config["RECORDINGS_DIR"]), "natif-1", args.language)
        print(f"Voix des locuteurs natifs chargées : {r['keys']} passages" + (f" ({len(r['incomplete'])} phrases incomplètes : ffmpeg absent ou morceau manquant)" if r["incomplete"] else ""))
    conn.close()
    if app.extensions["amira"]["engine"] is not None:
        app.extensions["amira"]["engine"].ready()  # charge le modèle en tâche de fond
    print(f"\nAmira ({args.language}) prête sur http://127.0.0.1:{args.port} — moteur : "
          f"{'modèle M2M100 + mémoire validée' if engine == 'm2m100' else 'mémoire validée seule (modèle, torch, transformers ou sentencepiece absent)'}\n"
          "Dans Chrome : ↻ sur Amira (chrome://extensions) ; la pastille passe à « Prêt ». Ctrl+C pour arrêter.\n")
    app.run(host="127.0.0.1", port=args.port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
