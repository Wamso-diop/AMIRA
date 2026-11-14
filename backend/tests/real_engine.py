"""Vrai moteur des tests @pytest.mark.model : dossier choisi comme en production (AMIRA_MODEL_DIR)."""
import os
from pathlib import Path

from amira import config
from amira.engine import from_config


def real_engine():
    cfg = config.load({**os.environ, "AMIRA_ENV": "development", "AMIRA_ENGINE": "m2m100"})
    cfg["MODEL_DIR"] = str(Path(__file__).parents[1] / cfg["MODEL_DIR"])
    return from_config(cfg)
