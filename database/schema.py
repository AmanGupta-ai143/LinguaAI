"""SQLite schema for LinguaAI.

Two tables are used:
  * translation_history - every completed translation (drives the dashboard)
  * favorites           - translations the user chose to keep
"""

TRANSLATION_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS translation_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    original_text   TEXT    NOT NULL,
    translated_text TEXT    NOT NULL,
    source_language TEXT    NOT NULL,
    target_language TEXT    NOT NULL,
    timestamp       TEXT    NOT NULL,
    character_count INTEGER NOT NULL
);
"""

FAVORITES_TABLE = """
CREATE TABLE IF NOT EXISTS favorites (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    original_text   TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    source_language TEXT NOT NULL,
    target_language TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_history_timestamp ON translation_history (timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_history_target ON translation_history (target_language);",
]

ALL_STATEMENTS = [TRANSLATION_HISTORY_TABLE, FAVORITES_TABLE, *INDEXES]


def create_tables(connection) -> None:
    """Create all tables and indexes if they do not exist yet."""
    for statement in ALL_STATEMENTS:
        connection.execute(statement)
    connection.commit()
