import pytest

from database.db_manager import DatabaseManager
from tests.fake_turso import FakeTurso


@pytest.fixture(params=["sqlite", "remote"])
def db(request, tmp_path):
    """Every database test runs twice: on local SQLite and through the hosted-DB HTTP adapter."""
    if request.param == "sqlite":
        return DatabaseManager(tmp_path / "test.db")
    return DatabaseManager(remote=("https://fake-db.turso.io", "secret"), session=FakeTurso("secret"))
