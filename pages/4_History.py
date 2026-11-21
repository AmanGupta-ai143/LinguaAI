"""Translation history."""
import streamlit as st

from components.dashboard_cards import empty_state
from components.sidebar import page_header
from components.translator_ui import reuse_in_translator, save_favorite_button
from database.db_manager import get_db

PAGE_SIZE = 10
db = get_db()
page_header("Translation history", "Everything you have translated, newest first.")

search = st.text_input("Search", placeholder="Search original or translated text...", label_visibility="collapsed")
total = db.count_history(search or None)

if total == 0:
    empty_state("No translations found" if search else "No history yet",
                "Try a different search term." if search else "Completed translations are stored here automatically.")
else:
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    top_l, top_r = st.columns([3, 1])
    page = top_l.number_input("Page", 1, pages, 1) if pages > 1 else 1
    top_l.caption(f"{total:,} translation(s)")
    with top_r.popover("🗑️ Clear all"):
        st.warning("This permanently deletes your whole history.")
        if st.button("Yes, delete everything", type="primary"):
            db.clear_history()
            st.rerun()

    for row in db.get_history(limit=PAGE_SIZE, offset=(int(page) - 1) * PAGE_SIZE, search=search or None):
        with st.container(border=True):
            st.caption(f"{row['timestamp']}  ·  {row['source_language']} → {row['target_language']}  ·  {row['character_count']:,} chars")
            c1, c2 = st.columns(2)
            c1.markdown("**Original**")
            c1.write(row["original_text"])
            c2.markdown("**Translation**")
            c2.write(row["translated_text"])
            b1, b2, b3, _ = st.columns([1.3, 1.6, 1, 3])
            with b1:
                if st.button("↻ Reuse", key=f"reuse_{row['id']}", use_container_width=True):
                    reuse_in_translator(row["original_text"], row["translated_text"],
                                        row["source_language"], row["target_language"])
            with b2:
                save_favorite_button(row["original_text"], row["translated_text"],
                                     row["source_language"], row["target_language"], f"fav_{row['id']}")
            with b3:
                if st.button("🗑️ Delete", key=f"del_{row['id']}", use_container_width=True):
                    db.delete_translation(row["id"])
                    st.rerun()
