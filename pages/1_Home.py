"""Home dashboard - KPIs and charts computed from the real translation history."""
import html
from datetime import date

import streamlit as st

from components import charts
from components.dashboard_cards import empty_state, onboarding_card, render_kpis
from components.sidebar import page_header, render_footer
from database.db_manager import get_db
from services import analytics
from services.translator import LANGUAGES

db = get_db()
stats = db.get_stats()
df = db.get_history_df()
total = stats["total_translations"]

page_header(
    "Welcome to LinguaAI 👋",
    "Translate text and documents with a real translation API - and watch your usage insights grow.",
    chips=[f"🌍 {len(LANGUAGES)} languages", "🔍 Auto-detect", "📄 PDF · DOCX · TXT", "🔊 Text-to-speech", "📊 Live analytics"],
)

# ---- quick actions
actions = [
    ("✍️", "Translate text", "Type or paste text and get an instant translation.", "Open translator", "pages/2_Translator.py"),
    ("📄", "Translate a document", "Upload a PDF, DOCX or TXT file.", "Upload document", "pages/3_Document_Translation.py"),
    ("🕘", "Browse history", "Search and reuse earlier translations.", "View history", "pages/4_History.py"),
]
for col, (icon, title, desc, label, target) in zip(st.columns(3), actions):
    with col, st.container(border=True):
        st.markdown(
            f'<div class="lg-action"><div class="title">{icon} {title}</div><div class="desc">{desc}</div></div>',
            unsafe_allow_html=True,
        )
        if st.button(label, key=f"qa_{target}", use_container_width=True, type="primary" if target.endswith("2_Translator.py") else "secondary"):
            st.switch_page(target)

st.write("")

# ---- KPI cards (every caption below is derived from stored records)
subs = {}
if total:
    today_count = int((df["timestamp"].dt.date == date.today()).sum()) if not df.empty else 0
    top_language = analytics.language_counts(df).iloc[0]["language"] if not df.empty else None
    subs = {
        "total": f"{today_count} today",
        "chars": f"≈ {round(stats['total_characters'] / total):,} per translation",
        "languages": f"Top target: {top_language}" if top_language else "",
        "favorites": "Saved for later",
    }
render_kpis(stats, subs)
st.write("")

if total == 0:
    onboarding_card()
    st.write("")
    if st.button("Make my first translation →", type="primary"):
        st.switch_page("pages/2_Translator.py")
else:
    NO_DATA = ("Not enough data yet", "Keep translating and this chart will fill in with your real usage.")

    def show(fig, key):
        if fig is None:
            empty_state(*NO_DATA)
        else:
            st.plotly_chart(fig, use_container_width=True, key=key)

    # activity over time
    with st.container(border=True):
        period = st.radio("Period", ["Daily", "Weekly", "Monthly"], horizontal=True, label_visibility="collapsed")
        show(charts.activity_chart(analytics.activity_over_time(df, period), period), "c_activity")

    # most used + distribution
    left, right = st.columns(2)
    with left, st.container(border=True):
        show(charts.most_used_chart(analytics.language_counts(df)), "c_most_used")
    with right, st.container(border=True):
        show(charts.distribution_chart(analytics.distribution(df)), "c_distribution")

    # source vs target + weekday
    left, right = st.columns(2)
    with left, st.container(border=True):
        show(charts.source_target_chart(analytics.source_vs_target(df)), "c_src_tgt")
    with right, st.container(border=True):
        show(charts.weekday_chart(analytics.weekday_counts(df)), "c_weekday")

    # recent activity
    st.subheader("Recent translations")

    def clip(text: str, n: int = 160) -> str:
        return html.escape(text[:n] + ("…" if len(text) > n else ""))

    for row in db.get_history(limit=5):
        st.markdown(
            f'<div class="lg-recent"><div class="meta"><span class="lg-pill">{html.escape(row["source_language"])} '
            f'<span class="arrow">→</span> {html.escape(row["target_language"])}</span> &nbsp; {row["timestamp"]}</div>'
            f'<div class="row"><div>{clip(row["original_text"])}</div><div>{clip(row["translated_text"])}</div></div></div>',
            unsafe_allow_html=True,
        )

    with st.expander("View chart data as a table"):
        st.dataframe(
            analytics.language_counts(df).rename(columns={"language": "Target language", "translations": "Translations"}),
            hide_index=True, use_container_width=True,
        )

render_footer()
