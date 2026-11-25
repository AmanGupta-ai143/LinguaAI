"""Tests for the SQLite layer and the analytics aggregations built on it."""
import pytest

from services.analytics import (
    activity_over_time,
    distribution,
    language_counts,
    source_vs_target,
    weekday_counts,
)


def add(db, text="Hello", out="नमस्ते", src="English", tgt="Hindi", ts=None):
    return db.add_translation(text, out, src, tgt, timestamp=ts)


# ------------------------------------------------------------------ history CRUD
def test_insert_and_retrieve(db):
    rid = add(db, "Hello world", "नमस्ते दुनिया")
    row = db.get_translation(rid)
    assert row["original_text"] == "Hello world"
    assert row["translated_text"] == "नमस्ते दुनिया"
    assert row["source_language"] == "English" and row["target_language"] == "Hindi"
    assert row["character_count"] == len("Hello world")
    assert row["timestamp"]


def test_newest_first_and_pagination(db):
    add(db, "a", "x", ts="2026-01-01 10:00:00")
    add(db, "b", "y", ts="2026-01-02 10:00:00")
    add(db, "c", "z", ts="2026-01-03 10:00:00")
    assert [r["original_text"] for r in db.get_history()] == ["c", "b", "a"]
    assert [r["original_text"] for r in db.get_history(limit=1, offset=1)] == ["b"]


def test_search_is_case_insensitive_and_escapes_wildcards(db):
    add(db, "Good Morning", "Bonjour")
    add(db, "100% sure", "certain")
    assert db.count_history("good") == 1
    assert db.count_history("100%") == 1      # % is treated literally
    assert db.count_history("%") == 1
    assert db.count_history("bonjour") == 1   # searches translated text too


def test_update_translation(db):
    rid = add(db)
    assert db.update_translation(rid, "हैलो")
    assert db.get_translation(rid)["translated_text"] == "हैलो"
    assert not db.update_translation(9999, "x")


def test_delete_and_clear(db):
    a, b = add(db), add(db)
    assert db.delete_translation(a) is True
    assert db.delete_translation(a) is False
    assert db.count_history() == 1
    assert db.clear_history() == 1
    assert db.get_translation(b) is None


def test_empty_values_rejected(db):
    with pytest.raises(ValueError):
        db.add_translation("", "x", "English", "Hindi")
    with pytest.raises(ValueError):
        db.add_favorite("x", "", "English", "Hindi")


def test_explicit_character_count_for_shortened_documents(db):
    rid = db.add_translation("a" * 8000, "b" * 8000, "English", "French", character_count=8000)
    row = db.get_translation(rid)
    assert row["character_count"] == 8000
    assert len(row["original_text"]) < 8000  # stored text is shortened


# ------------------------------------------------------------------ favorites
def test_favorites_crud_and_duplicates(db):
    fid, created = db.add_favorite("Hello", "नमस्ते", "English", "Hindi")
    assert created
    fid2, created2 = db.add_favorite("Hello", "नमस्ते", "English", "Hindi")
    assert fid2 == fid and not created2
    assert db.count_favorites() == 1
    assert db.remove_favorite(fid) is True
    assert db.remove_favorite(fid) is False
    assert db.count_favorites() == 0


def test_favorites_search(db):
    db.add_favorite("Hello", "Bonjour", "English", "French")
    db.add_favorite("Thanks", "धन्यवाद", "English", "Hindi")
    assert len(db.get_favorites()) == 2
    assert [f["original_text"] for f in db.get_favorites("hindi")] == ["Thanks"]
    assert [f["original_text"] for f in db.get_favorites("bonj")] == ["Hello"]


# ------------------------------------------------------------------ stats reflect real data
def test_stats_match_stored_records(db):
    for _ in range(15):
        add(db, "Hello", "नमस्ते", "English", "Hindi")
    add(db, "Bonjour", "Hello", "Auto-detect", "English")
    for i in range(5):
        db.add_favorite(f"t{i}", "x", "English", "Hindi")
    stats = db.get_stats()
    assert stats["total_translations"] == 16
    assert stats["total_characters"] == 15 * 5 + 7
    assert stats["languages_used"] == 2          # English, Hindi ("Auto-detect" excluded)
    assert stats["favorites"] == 5


def test_stats_on_empty_database(db):
    assert db.get_stats() == {"total_translations": 0, "total_characters": 0,
                              "languages_used": 0, "favorites": 0}
    assert db.get_history_df().empty


def test_history_df_and_charts_update_after_new_translation(db):
    assert language_counts(db.get_history_df()).empty
    add(db, "a", "b", ts="2026-03-02 09:00:00")
    df = db.get_history_df()
    assert language_counts(df)["translations"].tolist() == [1]
    add(db, "c", "d", tgt="French", ts="2026-03-02 10:00:00")
    df = db.get_history_df()
    assert language_counts(df).set_index("language")["translations"].to_dict() == {"Hindi": 1, "French": 1}


# ------------------------------------------------------------------ analytics
@pytest.fixture()
def df(db):
    # 15x English->Hindi, 3x English->French, 2x French->English
    # 2026-03-02 is a Monday
    for i in range(15):
        add(db, "Hello", "x", "English", "Hindi", ts=f"2026-03-02 {8 + i % 5:02d}:00:00")
    for i in range(3):
        add(db, "Hello", "x", "English", "French", ts="2026-03-04 12:00:00")
    for i in range(2):
        add(db, "Bonjour", "x", "French", "English", ts="2026-03-10 12:00:00")
    return db.get_history_df()


def test_language_counts_reflect_real_usage(df):
    counts = language_counts(df).set_index("language")["translations"].to_dict()
    assert counts == {"Hindi": 15, "French": 3, "English": 2}


def test_distribution_percentages_sum_to_100(df):
    dist = distribution(df, top_n=2)
    assert dist["percent"].sum() == pytest.approx(100)
    assert dist.set_index("language").loc["Hindi", "percent"] == pytest.approx(75)
    assert "Other" in dist["language"].tolist()


def test_daily_activity(df):
    daily = activity_over_time(df, "Daily").set_index("period")["translations"]
    assert daily.loc["2026-03-02"] == 15
    assert daily.loc["2026-03-03"] == 0           # real zero day between activity
    assert daily.sum() == 20


def test_weekly_activity_starts_on_monday(df):
    weekly = activity_over_time(df, "Weekly")
    assert weekly["period"].dt.day_name().eq("Monday").all()
    assert weekly["translations"].tolist() == [18, 2]   # week of Mar 2, week of Mar 9


def test_monthly_activity(df):
    monthly = activity_over_time(df, "Monthly")
    assert monthly["translations"].tolist() == [20]


def test_weekday_counts_cover_all_days(df):
    wd = weekday_counts(df).set_index("weekday")["translations"]
    assert list(wd.index)[0] == "Monday" and len(wd) == 7
    assert wd["Monday"] == 15 and wd["Wednesday"] == 3 and wd["Tuesday"] == 2


def test_source_vs_target(df):
    out = source_vs_target(df)
    lookup = {(r.language, r.role): r.translations for r in out.itertuples()}
    assert lookup[("English", "Source")] == 18
    assert lookup[("Hindi", "Target")] == 15
    assert lookup[("English", "Target")] == 2


def test_analytics_handle_empty_frames(db):
    empty = db.get_history_df()
    assert activity_over_time(empty).empty
    assert distribution(empty).empty
    assert source_vs_target(empty).empty
    assert weekday_counts(empty)["translations"].sum() == 0
