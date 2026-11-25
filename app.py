"""LinguaAI - entry point.

Run with:  streamlit run app.py
Sets up the page, shared styling, sign-in and sidebar, then hands over to the selected page.
"""
import sqlite3

import streamlit as st

from components.auth import is_logged_in, render_account_box, render_login
from components.sidebar import load_css, render_sidebar
from database.db_manager import get_db

st.set_page_config(
    page_title="LinguaAI - Smart Language Translation Platform",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="auto",
)

load_css()

try:
    db = get_db()
except sqlite3.Error as exc:
    st.error(f"The database could not be opened: {exc}")
    st.stop()

if not is_logged_in():
    render_login()
    st.stop()

render_sidebar()
render_account_box()
if db.fallback_reason:
    st.warning(
        "The cloud database is unreachable, so LinguaAI is using temporary storage - history may be lost "
        f"on restart. ({db.fallback_reason})"
    )

search_page = st.Page("pages/7_Search.py", title="Search", icon="🔍")
navigation = st.navigation(
    [
        st.Page("pages/1_Home.py", title="Home", icon="🏠", default=True),
        st.Page("pages/2_Translator.py", title="Translator", icon="🌐"),
        st.Page("pages/3_Document_Translation.py", title="Documents", icon="📄"),
        st.Page("pages/4_History.py", title="History", icon="🕘"),
        st.Page("pages/5_Favorites.py", title="Favorites", icon="⭐"),
        search_page,
        st.Page("pages/6_About.py", title="About", icon="ℹ️"),
    ]
)

if st.session_state.pop("_goto_search", False):
    st.switch_page(search_page)

try:
    navigation.run()
except sqlite3.Error as exc:
    st.error(f"Database problem: {exc}")
