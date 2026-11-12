import pytest

from amira import create_app

DEV = {"AMIRA_ENV": "development"}


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
