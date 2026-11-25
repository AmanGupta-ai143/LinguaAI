"""About the project."""
import streamlit as st

from components.sidebar import page_header, render_footer
from services.translator import LANGUAGES

page_header("About LinguaAI", "A multilingual translation platform built with Python and Streamlit.")

st.subheader("Introduction")
st.write(
    "LinguaAI translates text and documents between "
    f"{len(LANGUAGES)} languages using the MyMemory Translation API, keeps a searchable history, "
    "lets you save favorites, reads translations aloud and turns your usage into interactive charts."
)

st.subheader("Objective")
st.write(
    "Build a practical, well-structured Language Translation Tool that demonstrates Python, API integration, "
    "basic NLP ideas (language detection, text chunking), backend design, data processing and visualization."
)

st.subheader("Technology stack")
st.table({
    "Area": ["Language", "UI", "Translation", "Speech", "Data & charts", "Storage", "Documents"],
    "Technology": ["Python 3", "Streamlit + custom CSS", "MyMemory API via Requests", "gTTS",
                   "Pandas + Plotly", "SQLite", "pypdf, python-docx"],
})

st.subheader("Features")
st.markdown(
    "- Text translation with auto-detection, language swap, copy, and text-to-speech\n"
    "- Document translation (TXT, PDF, DOCX) with chunked processing and download\n"
    "- Accounts and guest mode - every user sees only their own history and statistics\n"
    "- Global search across history and favorites\n"
    "- Translation history with search, reuse and delete\n"
    "- Favorites with search\n"
    "- Dashboard with six chart types computed from real stored data\n"
    "- Input/file validation, timeouts, retries and friendly error messages"
)

st.subheader("System architecture")
st.code(
    "Streamlit pages (UI)  ->  components (cards, charts, widgets)\n"
    "        |\n"
    "        v\n"
    "services/ : translator | language_detector | speech | document_handler | analytics\n"
    "        |                      |\n"
    "        v                      v\n"
    "database/ (SQLite)     MyMemory API · gTTS\n",
    language="text",
)

st.subheader("Known limitations & future improvements")
st.markdown(
    "- MyMemory's free tier has a daily quota and modest quality for long or specialised text.\n"
    "- Scanned (image-only) PDFs are not supported - OCR would be a future addition.\n"
    "- Cloud history needs the optional hosted database (Turso); without it, data is temporary.\n"
    "- Accounts are simple (username + password, no recovery); guest data is deleted after 24 hours.\n"
    "- Planned: Google Cloud Translation / Microsoft Translator providers, e-mail verification and password reset, "
    "translated DOCX export, translation memory."
)

render_footer()
