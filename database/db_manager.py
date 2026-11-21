"""Database access layer (SQLite).

All SQL lives here so the UI never touches the database directly.
The database file location can be overridden with the LINGUAAI_DB_PATH
environment variable; by default it is ``data/linguaai.db`` inside the project.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd

from database.schema import create_tables

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "linguaai.db"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
# Texts stored from document translations are shortened to keep the DB small.
MAX_STORED_TEXT = 5000


def _now() -> str:
    return datetime.now().strftime(TIME_FORMAT)


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _shorten(text: str) -> str:
    if len(text) <= MAX_STORED_TEXT:
        return text
    return text[:MAX_STORED_TEXT] + " […]"


class DatabaseManager:
    """Thin wrapper around sqlite3 offering CRUD operations and statistics."""

    def __init__(self, db_path: Optional[str | Path] = None):
        path = db_path or os.environ.get("LINGUAAI_DB_PATH") or DEFAULT_DB_PATH
        self.db_path = Path(path)
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    # ------------------------------------------------------------------ plumbing
    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
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

    # ------------------------------------------------------------------ history
    def add_translation(
        self,
        original_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
        timestamp: Optional[str] = None,
        character_count: Optional[int] = None,
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
                "INSERT INTO translation_history (original_text, translated_text, "
                "source_language, target_language, timestamp, character_count) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    _shorten(original_text),
                    _shorten(translated_text),
                    source_language,
                    target_language,
                    timestamp or _now(),
                    count,
                ),
            )
            return int(cur.lastrowid)

    def get_history(
        self, limit: Optional[int] = None, offset: int = 0, search: Optional[str] = None
    ) -> list[dict]:
        """Return history rows, newest first, optionally filtered by text search."""
        query = "SELECT * FROM translation_history"
        params: list = []
        if search:
            query += " WHERE original_text LIKE ? ESCAPE '\\' OR translated_text LIKE ? ESCAPE '\\'"
            like = f"%{_escape_like(search)}%"
            params += [like, like]
        query += " ORDER BY timestamp DESC, id DESC"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params += [limit, offset]
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(query, params)]

    def count_history(self, search: Optional[str] = None) -> int:
        query = "SELECT COUNT(*) FROM translation_history"
        params: list = []
        if search:
            query += " WHERE original_text LIKE ? ESCAPE '\\' OR translated_text LIKE ? ESCAPE '\\'"
            like = f"%{_escape_like(search)}%"
            params += [like, like]
        with self._connect() as conn:
            return int(conn.execute(query, params).fetchone()[0])

    def get_translation(self, translation_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM translation_history WHERE id = ?", (translation_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_translation(self, translation_id: int, translated_text: str) -> bool:
        """Replace the stored translated text of a record (e.g. after a manual edit)."""
        if not translated_text:
            raise ValueError("translated_text must not be empty")
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE translation_history SET translated_text = ? WHERE id = ?",
                (_shorten(translated_text), translation_id),
            )
            return cur.rowcount > 0

    def delete_translation(self, translation_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM translation_history WHERE id = ?", (translation_id,))
            return cur.rowcount > 0

    def clear_history(self) -> int:
        with self._connect() as conn:
            return conn.execute("DELETE FROM translation_history").rowcount

    # ---------------------------------------------------------------- favorites
    def add_favorite(
        self, original_text: str, translated_text: str, source_language: str, target_language: str
    ) -> tuple[int, bool]:
        """Save a favorite. Returns ``(id, created)``; duplicates are not re-added."""
        if not original_text or not translated_text:
            raise ValueError("original_text and translated_text must not be empty")
        original_text, translated_text = _shorten(original_text), _shorten(translated_text)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM favorites WHERE original_text = ? AND translated_text = ? "
                "AND source_language = ? AND target_language = ?",
                (original_text, translated_text, source_language, target_language),
            ).fetchone()
            if existing:
                return int(existing["id"]), False
            cur = conn.execute(
                "INSERT INTO favorites (original_text, translated_text, source_language, "
                "target_language, created_at) VALUES (?, ?, ?, ?, ?)",
                (original_text, translated_text, source_language, target_language, _now()),
            )
            return int(cur.lastrowid), True

    def get_favorites(self, search: Optional[str] = None) -> list[dict]:
        query = "SELECT * FROM favorites"
        params: list = []
        if search:
            like = f"%{_escape_like(search)}%"
            query += (
                " WHERE original_text LIKE ? ESCAPE '\\' OR translated_text LIKE ? ESCAPE '\\'"
                " OR source_language LIKE ? ESCAPE '\\' OR target_language LIKE ? ESCAPE '\\'"
            )
            params += [like, like, like, like]
        query += " ORDER BY created_at DESC, id DESC"
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(query, params)]

    def remove_favorite(self, favorite_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM favorites WHERE id = ?", (favorite_id,))
            return cur.rowcount > 0

    def count_favorites(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0])

    # --------------------------------------------------------------- statistics
    def get_stats(self) -> dict:
        """Aggregate numbers for the KPI cards - computed from stored records only."""
        with self._connect() as conn:
            total, chars = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(character_count), 0) FROM translation_history"
            ).fetchone()
            languages_used = conn.execute(
                "SELECT COUNT(*) FROM ("
                " SELECT source_language AS lang FROM translation_history"
                " UNION SELECT target_language FROM translation_history"
                ") WHERE lang <> 'Auto-detect'"
            ).fetchone()[0]
        return {
            "total_translations": int(total),
            "total_characters": int(chars),
            "languages_used": int(languages_used),
            "favorites": self.count_favorites(),
        }

    def get_history_df(self) -> pd.DataFrame:
        """Whole history as a DataFrame with a parsed ``timestamp`` column."""
        rows = self.get_history()
        columns = [
            "id", "original_text", "translated_text", "source_language",
            "target_language", "timestamp", "character_count",
        ]
        df = pd.DataFrame(rows, columns=columns)
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df.dropna(subset=["timestamp"]).reset_index(drop=True)


_instance: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """Return a process-wide DatabaseManager (created on first use)."""
    global _instance
    if _instance is None:
        _instance = DatabaseManager()
    return _instance
