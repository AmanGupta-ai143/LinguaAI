"""Global search across the signed-in user's history and favorites."""
import html

import streamlit as st

from components.auth import current_db
from components.dashboard_cards import empty_state
from components.sidebar import page_header
from components.translator_ui import reuse_in_translator

MAX_RESULTS = 50
db = current_db()

page_header("Search", "Find any translation in your history or favorites.")

query = st.text_input(
    "Search", value=st.session_state.get("search_q", ""), placeholder="Type a word, phrase or language...",
    label_visibility="collapsed", key="search_page_input",
).strip()
st.session_state["search_q"] = query

if not query:
    empty_state("Start typing to search", "Searches original text, translations and language names.", icon="🔍")
    st.stop()

history = db.get_history(limit=MAX_RESULTS, search=query)
favorites = db.get_favorites(search=query)
st.caption(f"{db.count_history(search=query):,} in history · {len(favorites):,} in favorites for “{html.escape(query)}”")

tab_history, tab_favorites = st.tabs([f"History ({len(history)})", f"Favorites ({len(favorites)})"])


def show(rows, prefix, date_field):
    if not rows:
        empty_state("No matches", "Try a different word.", icon="🔎")
        return
    for row in rows:
        with st.container(border=True):
            st.caption(f"{row[date_field]}  ·  {row['source_language']} → {row['target_language']}")
            left, right = st.columns(2)
            left.write(row["original_text"])
            right.write(row["translated_text"])
            if st.button("↻ Reuse", key=f"{prefix}_{row['id']}"):
                reuse_in_translator(row["original_text"], row["translated_text"],
                                    row["source_language"], row["target_language"])


with tab_history:
    show(history, "sh", "timestamp")
with tab_favorites:
    show(favorites, "sf", "created_at")
