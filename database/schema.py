"""Database schema for LinguaAI (SQLite dialect - also valid for hosted libSQL/Turso).

Tables:
  * users               - accounts (and short-lived guest sessions)
  * translation_history - every completed translation (drives the dashboard)
  * favorites           - translations the user chose to keep

``history`` and ``favorites`` carry a ``user_id`` so each visitor only sees their own data.
"""

USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL,
    password_hash TEXT    NOT NULL,
    salt          TEXT    NOT NULL,
    created_at    TEXT    NOT NULL,
    is_guest      INTEGER NOT NULL DEFAULT 0
);
"""

TRANSLATION_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS translation_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    original_text   TEXT    NOT NULL,
    translated_text TEXT    NOT NULL,
    source_language TEXT    NOT NULL,
    target_language TEXT    NOT NULL,
    timestamp       TEXT    NOT NULL,
    character_count INTEGER NOT NULL,
    user_id         INTEGER NOT NULL DEFAULT 0
);
"""

FAVORITES_TABLE = """
CREATE TABLE IF NOT EXISTS favorites (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    original_text   TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    source_language TEXT NOT NULL,
    target_language TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    user_id         INTEGER NOT NULL DEFAULT 0
);
"""

TABLES = [USERS_TABLE, TRANSLATION_HISTORY_TABLE, FAVORITES_TABLE]

# Indexes are created after migrations because they reference ``user_id``.
INDEXES = [
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users (username COLLATE NOCASE);",
    "CREATE INDEX IF NOT EXISTS idx_history_user_time ON translation_history (user_id, timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_history_user_target ON translation_history (user_id, target_language);",
    "CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites (user_id, created_at);",
]


def _columns(connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]


def migrate(connection) -> None:
    """Upgrade databases created by older versions (no ``user_id`` column)."""
    for table in ("translation_history", "favorites"):
        if "user_id" not in _columns(connection, table):
            connection.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0")


def create_tables(connection) -> None:
    """Create tables, migrate old ones, then create indexes."""
    for statement in TABLES:
        connection.execute(statement)
    migrate(connection)
    for statement in INDEXES:
        connection.execute(statement)
    connection.commit()
