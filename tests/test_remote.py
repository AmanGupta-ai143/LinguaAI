"""The hosted-database HTTP adapter: request encoding, response decoding, error handling."""
import sqlite3
from unittest.mock import MagicMock

import pytest
import requests

from database import db_manager
from database.db_manager import DatabaseManager
from database.remote import RemoteConnection, RemoteDBError, normalize_url, remote_config_from_env
from tests.fake_turso import FakeResponse, FakeTurso


def conn(session, url="https://x.turso.io", token="secret"):
    return RemoteConnection(url, token, session=session)


def test_url_normalisation():
    assert normalize_url("libsql://db-org.turso.io") == "https://db-org.turso.io"
    assert normalize_url("https://db-org.turso.io/") == "https://db-org.turso.io"
    assert normalize_url("db-org.turso.io") == "https://db-org.turso.io"
    # common paste mistakes
    assert normalize_url('  "libsql://db-org.turso.io"\n') == "https://db-org.turso.io"
    assert normalize_url("https://db-org.turso.io/v2/pipeline") == "https://db-org.turso.io"
    assert normalize_url("libsql://db-org.turso.io?authToken=abc") == "https://db-org.turso.io"


def test_request_format_and_value_decoding():
    fake = FakeTurso()
    c = conn(fake)
    c.execute("CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT, a TEXT, b INTEGER, c REAL, d TEXT)")
    cur = c.execute("INSERT INTO t (a, b, c, d) VALUES (?, ?, ?, ?)", ("héllo नमस्ते", 7, 1.5, None))
    assert cur.lastrowid == 1 and cur.rowcount == 1
    row = c.execute("SELECT * FROM t WHERE a = ?", ("héllo नमस्ते",)).fetchone()
    assert dict(row) == {"id": 1, "a": "héllo नमस्ते", "b": 7, "c": 1.5, "d": None}
    assert row["a"] == row[1] and list(row)[0] == 1

    last = fake.requests[-1]
    assert last["url"] == "https://x.turso.io/v2/pipeline"
    assert last["headers"]["Authorization"] == "Bearer secret"
    body = last["json"]["requests"]
    assert body[0]["stmt"]["args"] == [{"type": "text", "value": "héllo नमस्ते"}]
    assert body[-1] == {"type": "close"}
    assert last["timeout"]                                            # never waits forever


def test_integer_args_are_sent_as_strings():
    fake = FakeTurso()
    c = conn(fake)
    c.execute("CREATE TABLE t (n INTEGER)")
    c.execute("INSERT INTO t VALUES (?)", (42,))
    assert fake.requests[-1]["json"]["requests"][0]["stmt"]["args"] == [{"type": "integer", "value": "42"}]


def test_sql_error_is_reported():
    with pytest.raises(RemoteDBError, match="no such table"):
        conn(FakeTurso()).execute("SELECT * FROM missing")


def test_wrong_token_gives_clear_message():
    with pytest.raises(RemoteDBError, match="authentication"):
        conn(FakeTurso("secret"), token="wrong").execute("SELECT 1")


@pytest.mark.parametrize("exc, text", [(requests.Timeout(), "too long"), (requests.ConnectionError(), "Could not reach")])
def test_network_failures(exc, text):
    session = MagicMock()
    session.post.side_effect = exc
    with pytest.raises(RemoteDBError, match=text):
        conn(session).execute("SELECT 1")


def test_server_errors_and_garbage_responses():
    session = MagicMock()
    session.post.return_value = FakeResponse(500, {"error": "boom"})
    with pytest.raises(RemoteDBError, match="HTTP 500"):
        conn(session).execute("SELECT 1")
    session.post.return_value = FakeResponse(200, {"unexpected": True})
    with pytest.raises(RemoteDBError, match="Unexpected"):
        conn(session).execute("SELECT 1")


def test_404_names_the_host_so_typos_are_visible():
    session = MagicMock()
    session.post.return_value = FakeResponse(404, {})
    with pytest.raises(RemoteDBError, match=r"HTTP 404\) at wrong-db-org\.turso\.io"):
        conn(session, url="libsql://wrong-db-org.turso.io").execute("SELECT 1")


def test_remote_errors_are_catchable_as_sqlite_errors():
    """Pages already catch sqlite3.Error, so hosted-DB failures show friendly messages too."""
    assert issubclass(RemoteDBError, sqlite3.Error)


def test_config_from_environment(monkeypatch):
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    assert remote_config_from_env() is None
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://db-org.turso.io")
    assert remote_config_from_env() is None                           # token missing -> stay local
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "tok")
    assert remote_config_from_env() == ("https://db-org.turso.io", "tok")


def test_manager_backend_selection(monkeypatch, tmp_path):
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://db-org.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "tok")
    assert DatabaseManager(tmp_path / "x.db").backend == "sqlite"     # explicit path wins
    assert DatabaseManager(session=FakeTurso("tok")).backend == "remote"


def test_get_db_falls_back_to_sqlite_when_hosted_db_is_down(monkeypatch, tmp_path):
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://db-org.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "tok")
    monkeypatch.setenv("LINGUAAI_DB_PATH", str(tmp_path / "fallback.db"))
    monkeypatch.setattr(db_manager, "_instance", None)
    real = requests.Session

    class Down(real):
        def post(self, *a, **k):
            raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "Session", Down)
    db = db_manager.get_db()
    assert db.backend == "sqlite" and "Could not reach" in db.fallback_reason
    monkeypatch.setattr(db_manager, "_instance", None)


def test_timestamps_follow_configured_timezone(monkeypatch):
    monkeypatch.setenv("LINGUAAI_TZ", "Asia/Kolkata")
    kolkata = db_manager.now_local()
    monkeypatch.setenv("LINGUAAI_TZ", "UTC")
    utc = db_manager.now_local()
    assert (kolkata.utcoffset().total_seconds() - utc.utcoffset().total_seconds()) == 5.5 * 3600
