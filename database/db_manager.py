"""Database access layer.

All SQL lives here so the UI never touches the database directly.

Storage backends (chosen automatically):
  1. A hosted libSQL / Turso database when ``TURSO_DATABASE_URL`` and ``TURSO_AUTH_TOKEN``
     are set (data survives restarts - recommended for deployment).
  2. Otherwise a local SQLite file (``data/linguaai.db`` or ``LINGUAAI_DB_PATH``).

Every history / favorites method takes a ``user_id`` so visitors only ever see their own
data. ``ScopedDB`` binds a user id once so pages don't have to pass it around.
"""
from __future__ import annotations

import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd
import requests

from database.remote import RemoteConnection, remote_config_from_env
from database.schema import create_tables
from services import auth as auth_utils

try:  # zoneinfo needs the `tzdata` package on Windows (listed in requirements.txt)
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "linguaai.db"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
GUEST_LIFETIME_HOURS = 24
# Long texts (documents) are shortened when stored to keep the database small.
MAX_STORED_TEXT = 5000


def now_local() -> datetime:
    """Current time in ``LINGUAAI_TZ`` (e.g. "Asia/Kolkata"), else the machine's local time."""
    name = os.environ.get("LINGUAAI_TZ", "").strip()
    if name and ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(name))
        except Exception:
            pass
    return datetime.now()


def _now() -> str:
    return now_local().strftime(TIME_FORMAT)


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _shorten(text: str) -> str:
    return text if len(text) <= MAX_STORED_TEXT else text[:MAX_STORED_TEXT] + " […]"


def _like_clause(search: Optional[str], columns: list[str]) -> tuple[str, list]:
    """``(" AND (a LIKE ? ... )", params)`` or ``("", [])`` when there is no search term."""
    if not search:
        return "", []
    like = f"%{_escape_like(search)}%"
    clause = " AND (" + " OR ".join(f"{c} LIKE ? ESCAPE '\\'" for c in columns) + ")"
    return clause, [like] * len(columns)


class DatabaseManager:
    """CRUD operations, accounts and statistics on top of SQLite or hosted libSQL."""

    HISTORY_SEARCH_COLUMNS = ["original_text", "translated_text"]
    FAVORITE_SEARCH_COLUMNS = ["original_text", "translated_text", "source_language", "target_language"]

    def __init__(self, db_path: Optional[str | Path] = None, remote: Optional[tuple[str, str]] = None, session=None):
        """``db_path`` forces local SQLite; ``remote=(url, token)`` forces the hosted database."""
        self.fallback_reason: Optional[str] = None
        self._session = session
        if db_path is not None:
            self._remote = None
        elif remote is not None:
            self._remote = remote
        else:
            self._remote = remote_config_from_env()
        if self._remote is not None and self._session is None:
            self._session = requests.Session()      # one keep-alive connection, reused for every query
        if self._remote is None:
            path = db_path or os.environ.get("LINGUAAI_DB_PATH") or DEFAULT_DB_PATH
            self.db_path = Path(path)
            if str(self.db_path) != ":memory:":
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.db_path = None
        self.initialize()

    @property
    def backend(self) -> str:
        return "remote" if self._remote else "sqlite"

    # ------------------------------------------------------------------ plumbing
    @contextmanager
    def _connect(self) -> Iterator:
        if self._remote:
            yield RemoteConnection(self._remote[0], self._remote[1], session=self._session)
            return
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self._connect() as conn:
            create_tables(conn)
        self.purge_guests()

    # ------------------------------------------------------------------ accounts
    def create_user(self, username: str, password: str) -> dict:
        username = auth_utils.validate_username(username)
        auth_utils.validate_password(password)
        with self._connect() as conn:
            if conn.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone():
                raise ValueError("That username is already taken.")
            password_hash, salt = auth_utils.hash_password(password)
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, salt, created_at, is_guest) VALUES (?, ?, ?, ?, 0)",
                (username, password_hash, salt, _now()),
            )
            return {"id": int(cur.lastrowid), "username": username, "is_guest": False}

    def authenticate(self, username: str, password: str) -> Optional[dict]:
        """Return the user dict for valid credentials, else ``None``."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, salt FROM users WHERE username = ? COLLATE NOCASE AND is_guest = 0",
                ((username or "").strip(),),
            ).fetchone()
        if row is None:
            auth_utils.verify_password(password or "", "0" * 64, "00" * 16)  # keep timing similar
            return None
        if not auth_utils.verify_password(password or "", row["password_hash"], row["salt"]):
            return None
        return {"id": int(row["id"]), "username": row["username"], "is_guest": False}

    def create_guest(self) -> dict:
        """A temporary account whose data is deleted after ``GUEST_LIFETIME_HOURS``."""
        name = f"guest-{secrets.token_hex(4)}"
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, salt, created_at, is_guest) VALUES (?, '', '', ?, 1)",
                (name, _now()),
            )
            return {"id": int(cur.lastrowid), "username": name, "is_guest": True}

    def purge_guests(self, max_age_hours: int = GUEST_LIFETIME_HOURS) -> int:
        """Delete guest accounts (and their data) older than ``max_age_hours``."""
        cutoff = (now_local() - timedelta(hours=max_age_hours)).strftime(TIME_FORMAT)
        old = "(SELECT id FROM users WHERE is_guest = 1 AND created_at < ?)"
        with self._connect() as conn:
            conn.execute(f"DELETE FROM translation_history WHERE user_id IN {old}", (cutoff,))
            conn.execute(f"DELETE FROM favorites WHERE user_id IN {old}", (cutoff,))
            return conn.execute("DELETE FROM users WHERE is_guest = 1 AND created_at < ?", (cutoff,)).rowcount

    # ------------------------------------------------------------------ history
    def add_translation(
        self,
        original_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
        timestamp: Optional[str] = None,
        character_count: Optional[int] = None,
        user_id: int = 0,
    ) -> int:
        """Insert a translation record and return its id.

        ``character_count`` defaults to the length of the original text; pass it
        explicitly when the stored text was shortened (e.g. long documents).
        """
        if not original_text or not translated_text:
            raise ValueError("original_text and translated_text must not be empty")
        count = character_count if character_count is not None else len(original_text)
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO translation_history (original_text, translated_text, source_language, "
                "target_language, timestamp, character_count, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (_shorten(original_text), _shorten(translated_text), source_language,
                 target_language, timestamp or _now(), count, user_id),
            )
            return int(cur.lastrowid)

    def get_history(
        self, limit: Optional[int] = None, offset: int = 0, search: Optional[str] = None, user_id: int = 0
    ) -> list[dict]:
        """Return history rows, newest first, optionally filtered by text search."""
        clause, params = _like_clause(search, self.HISTORY_SEARCH_COLUMNS)
        query = f"SELECT * FROM translation_history WHERE user_id = ?{clause} ORDER BY timestamp DESC, id DESC"
        params = [user_id, *params]
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params += [limit, offset]
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(query, params)]

    def count_history(self, search: Optional[str] = None, user_id: int = 0) -> int:
        clause, params = _like_clause(search, self.HISTORY_SEARCH_COLUMNS)
        with self._connect() as conn:
            return int(conn.execute(
                f"SELECT COUNT(*) FROM translation_history WHERE user_id = ?{clause}", [user_id, *params]
            ).fetchone()[0])

    def get_translation(self, translation_id: int, user_id: int = 0) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM translation_history WHERE id = ? AND user_id = ?", (translation_id, user_id)
            ).fetchone()
            return dict(row) if row else None

    def update_translation(self, translation_id: int, translated_text: str, user_id: int = 0) -> bool:
        """Replace the stored translated text of a record (e.g. after a manual edit)."""
        if not translated_text:
            raise ValueError("translated_text must not be empty")
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE translation_history SET translated_text = ? WHERE id = ? AND user_id = ?",
                (_shorten(translated_text), translation_id, user_id),
            )
            return cur.rowcount > 0

    def delete_translation(self, translation_id: int, user_id: int = 0) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM translation_history WHERE id = ? AND user_id = ?", (translation_id, user_id)
            )
            return cur.rowcount > 0

    def clear_history(self, user_id: int = 0) -> int:
        with self._connect() as conn:
            return conn.execute("DELETE FROM translation_history WHERE user_id = ?", (user_id,)).rowcount

    # ---------------------------------------------------------------- favorites
    def add_favorite(
        self, original_text: str, translated_text: str, source_language: str, target_language: str,
        user_id: int = 0,
    ) -> tuple[int, bool]:
        """Save a favorite. Returns ``(id, created)``; duplicates are not re-added."""
        if not original_text or not translated_text:
            raise ValueError("original_text and translated_text must not be empty")
        original_text, translated_text = _shorten(original_text), _shorten(translated_text)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM favorites WHERE original_text = ? AND translated_text = ? "
                "AND source_language = ? AND target_language = ? AND user_id = ?",
                (original_text, translated_text, source_language, target_language, user_id),
            ).fetchone()
            if existing:
                return int(existing["id"]), False
            cur = conn.execute(
                "INSERT INTO favorites (original_text, translated_text, source_language, "
                "target_language, created_at, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                (original_text, translated_text, source_language, target_language, _now(), user_id),
            )
            return int(cur.lastrowid), True

    def get_favorites(self, search: Optional[str] = None, user_id: int = 0) -> list[dict]:
        clause, params = _like_clause(search, self.FAVORITE_SEARCH_COLUMNS)
        query = f"SELECT * FROM favorites WHERE user_id = ?{clause} ORDER BY created_at DESC, id DESC"
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(query, [user_id, *params])]

    def remove_favorite(self, favorite_id: int, user_id: int = 0) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM favorites WHERE id = ? AND user_id = ?", (favorite_id, user_id))
            return cur.rowcount > 0

    def count_favorites(self, user_id: int = 0) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM favorites WHERE user_id = ?", (user_id,)).fetchone()[0])

    # --------------------------------------------------------------- statistics
    def get_stats(self, user_id: int = 0) -> dict:
        """Aggregate numbers for the KPI cards - computed from stored records only."""
        with self._connect() as conn:
            total, chars = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(character_count), 0) FROM translation_history WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            languages_used = conn.execute(
                "SELECT COUNT(*) FROM ("
                " SELECT source_language AS lang FROM translation_history WHERE user_id = ?"
                " UNION SELECT target_language FROM translation_history WHERE user_id = ?"
                ") WHERE lang <> 'Auto-detect'",
                (user_id, user_id),
            ).fetchone()[0]
        return {
            "total_translations": int(total),
            "total_characters": int(chars),
            "languages_used": int(languages_used),
            "favorites": self.count_favorites(user_id),
        }

    def get_history_df(self, user_id: int = 0) -> pd.DataFrame:
        """A user's whole history as a DataFrame with a parsed ``timestamp`` column."""
        rows = self.get_history(user_id=user_id)
        columns = [
            "id", "original_text", "translated_text", "source_language",
            "target_language", "timestamp", "character_count",
        ]
        df = pd.DataFrame([{c: r[c] for c in columns} for r in rows], columns=columns)
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df.dropna(subset=["timestamp"]).reset_index(drop=True)


class ScopedDB:
    """A ``DatabaseManager`` view bound to one user - ``user_id`` is passed automatically."""

    _SCOPED = {
        "add_translation", "get_history", "count_history", "get_translation", "update_translation",
        "delete_translation", "clear_history", "add_favorite", "get_favorites", "remove_favorite",
        "count_favorites", "get_stats", "get_history_df",
    }

    def __init__(self, db: DatabaseManager, user_id: int):
        self._db = db
        self.user_id = user_id

    def __getattr__(self, name: str):
        attr = getattr(self._db, name)
        return partial(attr, user_id=self.user_id) if name in self._SCOPED else attr


_instance: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """Return a process-wide DatabaseManager (created on first use).

    If a hosted database is configured but unreachable, fall back to local SQLite and
    record why in ``fallback_reason`` so the UI can warn the user instead of crashing.
    """
    global _instance
    if _instance is None:
        try:
            _instance = DatabaseManager()
        except sqlite3.Error as exc:
            if remote_config_from_env() is None:
                raise
            _instance = DatabaseManager(db_path=os.environ.get("LINGUAAI_DB_PATH") or DEFAULT_DB_PATH)
            _instance.fallback_reason = str(exc)
    return _instance
