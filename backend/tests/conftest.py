import pytest

from amira import create_app, db
from gold import GOLD
from tools.import_gold import import_gold

DEV = {"AMIRA_ENV": "development", "AMIRA_DB_PATH": ":memory:"}


class FakeEngine:
    """Moteur factice : prêt ou non, et ne traduit rien en S1."""

    def __init__(self, loaded: bool = True):
        self.loaded = loaded

    def ready(self) -> bool:
        return self.loaded


@pytest.fixture
def app():
    return create_app(DEV, engine=FakeEngine())


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "amira.sqlite3")
    import_gold(db.connect(path), GOLD, "natif-1")
    return path


@pytest.fixture
def gold_app(db_path):
    """Application dont la mémoire contient le CSV gold."""
    return create_app({**DEV, "AMIRA_DB_PATH": db_path}, engine=FakeEngine())
