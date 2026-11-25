"""Accounts, guest sessions and per-user data isolation (run on both backends)."""
import sqlite3

import pytest

from database.db_manager import DatabaseManager, ScopedDB
from services import auth


# ------------------------------------------------------------------ password helpers
def test_password_hash_roundtrip_and_salting():
    h1, s1 = auth.hash_password("correct horse")
    h2, s2 = auth.hash_password("correct horse")
    assert s1 != s2 and h1 != h2                      # random salt per user
    assert auth.verify_password("correct horse", h1, s1)
    assert not auth.verify_password("wrong", h1, s1)
    assert "correct horse" not in h1


@pytest.mark.parametrize("name", ["ab", "a" * 31, "bad name", "bad@name", "", "guest-1234", "Guest-abcd"])
def test_invalid_usernames(name):
    with pytest.raises(ValueError):
        auth.validate_username(name)


def test_password_length_rules():
    with pytest.raises(ValueError):
        auth.validate_password("12345")
    with pytest.raises(ValueError):
        auth.validate_password("x" * 129)
    assert auth.validate_password("123456") == "123456"


# ------------------------------------------------------------------ users
def test_register_and_login(db):
    user = db.create_user("Aman", "secret1")
    assert user["username"] == "Aman" and not user["is_guest"]
    assert db.authenticate("Aman", "secret1")["id"] == user["id"]
    assert db.authenticate("aman", "secret1")["id"] == user["id"]      # case-insensitive
    assert db.authenticate("Aman", "nope12") is None
    assert db.authenticate("ghost", "secret1") is None


def test_duplicate_username_rejected_case_insensitively(db):
    db.create_user("Aman", "secret1")
    with pytest.raises(ValueError, match="taken"):
        db.create_user("AMAN", "another1")


def test_password_is_not_stored_in_plain_text(db):
    db.create_user("Aman", "secret1")
    with db._connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = 'Aman'").fetchone()
    assert "secret1" not in " ".join(str(v) for v in row)


def test_guests_cannot_log_in_and_expire(db):
    guest = db.create_guest()
    assert guest["is_guest"] and guest["username"].startswith("guest-")
    assert db.authenticate(guest["username"], "") is None
    scoped = ScopedDB(db, guest["id"])
    scoped.add_translation("Hello", "Bonjour", "English", "French")
    scoped.add_favorite("Hello", "Bonjour", "English", "French")
    keeper = db.create_user("keeper", "secret1")
    ScopedDB(db, keeper["id"]).add_translation("Keep", "Garder", "English", "French")

    assert db.purge_guests(max_age_hours=24) == 0                     # too new to delete
    assert db.purge_guests(max_age_hours=-1) == 1                     # force-expire
    assert db.count_history(user_id=guest["id"]) == 0
    assert db.count_favorites(user_id=guest["id"]) == 0
    assert db.count_history(user_id=keeper["id"]) == 1                # real users untouched
    assert db.authenticate("keeper", "secret1")


# ------------------------------------------------------------------ isolation
def test_users_only_see_their_own_data(db):
    a, b = db.create_user("alice", "secret1"), db.create_user("bobby", "secret1")
    A, B = ScopedDB(db, a["id"]), ScopedDB(db, b["id"])
    ida = A.add_translation("Hello", "Bonjour", "English", "French")
    B.add_translation("Thanks", "Merci", "English", "French")
    B.add_translation("Bye", "Au revoir", "English", "French")
    A.add_favorite("Hello", "Bonjour", "English", "French")

    assert [r["original_text"] for r in A.get_history()] == ["Hello"]
    assert len(B.get_history()) == 2
    assert A.get_stats()["total_translations"] == 1 and B.get_stats()["total_translations"] == 2
    assert A.get_stats()["favorites"] == 1 and B.get_stats()["favorites"] == 0
    assert A.count_history("Thanks") == 0                              # search is scoped too
    assert B.get_favorites() == [] and len(A.get_favorites()) == 1
    assert len(A.get_history_df()) == 1 and len(B.get_history_df()) == 2


def test_users_cannot_modify_or_delete_others_records(db):
    a, b = db.create_user("alice", "secret1"), db.create_user("bobby", "secret1")
    A, B = ScopedDB(db, a["id"]), ScopedDB(db, b["id"])
    rid = A.add_translation("Hello", "Bonjour", "English", "French")
    fid, _ = A.add_favorite("Hello", "Bonjour", "English", "French")

    assert B.get_translation(rid) is None
    assert B.delete_translation(rid) is False
    assert B.update_translation(rid, "hacked") is False
    assert B.remove_favorite(fid) is False
    assert B.clear_history() == 0
    assert A.get_translation(rid)["translated_text"] == "Bonjour"
    assert len(A.get_favorites()) == 1


def test_same_favorite_can_exist_for_two_users(db):
    A, B = ScopedDB(db, 1), ScopedDB(db, 2)
    assert A.add_favorite("Hi", "Salut", "English", "French")[1] is True
    assert B.add_favorite("Hi", "Salut", "English", "French")[1] is True


# ------------------------------------------------------------------ migration
def test_legacy_database_is_migrated(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE translation_history (id INTEGER PRIMARY KEY AUTOINCREMENT, original_text TEXT NOT NULL,"
                 " translated_text TEXT NOT NULL, source_language TEXT NOT NULL, target_language TEXT NOT NULL,"
                 " timestamp TEXT NOT NULL, character_count INTEGER NOT NULL)")
    conn.execute("CREATE TABLE favorites (id INTEGER PRIMARY KEY AUTOINCREMENT, original_text TEXT NOT NULL,"
                 " translated_text TEXT NOT NULL, source_language TEXT NOT NULL, target_language TEXT NOT NULL,"
                 " created_at TEXT NOT NULL)")
    conn.execute("INSERT INTO translation_history VALUES (1,'Hello','Bonjour','English','French','2026-01-01 10:00:00',5)")
    conn.commit(); conn.close()

    db = DatabaseManager(path)
    assert db.get_history()[0]["original_text"] == "Hello"            # legacy rows kept (user_id 0)
    assert ScopedDB(db, 5).get_history() == []                        # and invisible to real users
    db.create_user("alice", "secret1")
