"""LinguaAI - entry point.

Run with:  streamlit run app.py
Sets up the page, shared styling and sidebar, then hands over to the selected page.
"""
import streamlit as st

from components.sidebar import load_css, render_sidebar

st.set_page_config(
    page_title="LinguaAI - Smart Language Translation Platform",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="auto",
)

load_css()
render_sidebar()

navigation = st.navigation(
    [
        st.Page("pages/1_Home.py", title="Home", icon="🏠", default=True),
        st.Page("pages/2_Translator.py", title="Translator", icon="🌐"),
        st.Page("pages/3_Document_Translation.py", title="Documents", icon="📄"),
        st.Page("pages/4_History.py", title="History", icon="🕘"),
        st.Page("pages/5_Favorites.py", title="Favorites", icon="⭐"),
        st.Page("pages/6_About.py", title="About", icon="ℹ️"),
    ]
)
navigation.run()
