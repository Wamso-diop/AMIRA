from dotenv import load_dotenv

from amira import create_app, db

load_dotenv()  # avant create_app, qui lit os.environ
app = create_app()
db.purge(db.connect(app.config["DB_PATH"]), app.config["RETENTION_DAYS"])  # rétention, à chaque démarrage

engine = app.extensions["amira"]["engine"]
if engine is not None:
    engine.ready()  # lance le chargement du modèle dès le démarrage (/v1/ready répond 503 d'ici là)
