from dotenv import load_dotenv

from amira import create_app

load_dotenv()  # avant create_app, qui lit os.environ
app = create_app()

engine = app.extensions["amira"]["engine"]
if engine is not None:
    engine.ready()  # lance le chargement du modèle dès le démarrage (/v1/ready répond 503 d'ici là)
