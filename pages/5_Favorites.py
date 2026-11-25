"""Favorite translations."""
import streamlit as st

from components.dashboard_cards import empty_state
from components.sidebar import page_header
from components.translator_ui import reuse_in_translator
from components.auth import current_db

db = current_db()
page_header("Favorites", "Translations you saved for later.")

search = st.text_input("Search", placeholder="Search text or language...", label_visibility="collapsed")
favorites = db.get_favorites(search or None)

if not favorites:
    if search:
        empty_state("No matches", "Try a different search term.")
    else:
        empty_state("No favorites yet", "Use “Save to favorites” on the Translator or History page.")
else:
    st.caption(f"{len(favorites)} favorite(s)")
    cols = st.columns(2)
    for i, fav in enumerate(favorites):
        with cols[i % 2], st.container(border=True):
            st.markdown(f'<span class="lg-pill">{fav["source_language"]} → {fav["target_language"]}</span>', unsafe_allow_html=True)
            st.caption(f"Saved {fav['created_at']}")
            st.markdown("**Original**")
            st.write(fav["original_text"])
            st.markdown("**Translation**")
            st.write(fav["translated_text"])
            b1, b2 = st.columns(2)
            with b1:
                if st.button("↻ Reuse", key=f"fr_{fav['id']}", use_container_width=True):
                    reuse_in_translator(fav["original_text"], fav["translated_text"],
                                        fav["source_language"], fav["target_language"])
            with b2:
                if st.button("Remove", key=f"fd_{fav['id']}", use_container_width=True):
                    db.remove_favorite(fav["id"])
                    st.rerun()
