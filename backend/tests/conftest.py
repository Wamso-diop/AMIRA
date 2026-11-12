import shutil

import pytest

from amira import create_app, db
from amira.engine import FakeEngine
from gold import GOLD
from tools.import_gold import import_gold

DEV = {"AMIRA_ENV": "development", "AMIRA_DB_PATH": ":memory:", "AMIRA_ENGINE": "memory"}


@pytest.fixture
def app():
    return create_app(DEV, engine=FakeEngine())


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def gold_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("gold") / "amira.sqlite3"
    conn = db.connect(str(path))
    import_gold(conn, GOLD, "natif-1")
    conn.close()
    return path


@pytest.fixture
def db_path(gold_db, tmp_path):
    """Copie de la base gold, propre à chaque test."""
    path = tmp_path / "amira.sqlite3"
    shutil.copyfile(gold_db, path)
    return str(path)


@pytest.fixture
def gold_app(db_path):
    """Application dont la mémoire contient le CSV gold, sans moteur (AMIRA_ENGINE=memory)."""
    return create_app({**DEV, "AMIRA_DB_PATH": db_path}, engine=None)
