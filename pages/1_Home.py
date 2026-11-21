"""Home dashboard - KPIs and charts computed from the real translation history."""
import streamlit as st

from components import charts
from components.dashboard_cards import empty_state, render_kpis
from components.sidebar import page_header, render_footer
from database.db_manager import get_db
from services import analytics
from services.translator import LANGUAGES

db = get_db()
stats = db.get_stats()
df = db.get_history_df()

page_header("Welcome to LinguaAI 👋", "Translate text and documents with a real translation API - and watch your usage insights grow.")

top_left, top_right = st.columns([3, 1])
with top_left:
    st.markdown(f'<span class="lg-pill">{len(LANGUAGES)} languages supported</span>', unsafe_allow_html=True)
with top_right:
    if st.button("⚡ Quick translate", type="primary", use_container_width=True):
        st.switch_page("pages/2_Translator.py")

st.write("")
render_kpis(stats)
st.write("")

NO_DATA = ("No translations yet", "Translate something and this chart will fill in with your real usage.")


def show(fig, key):
    if fig is None:
        empty_state(*NO_DATA)
    else:
        st.plotly_chart(fig, use_container_width=True, key=key)


# Row 2 - activity over time
with st.container(border=True):
    period = st.radio("Period", ["Daily", "Weekly", "Monthly"], horizontal=True, label_visibility="collapsed")
    show(charts.activity_chart(analytics.activity_over_time(df, period), period), "c_activity")

# Row 3 - most used + distribution
left, right = st.columns(2)
with left, st.container(border=True):
    show(charts.most_used_chart(analytics.language_counts(df)), "c_most_used")
with right, st.container(border=True):
    show(charts.distribution_chart(analytics.distribution(df)), "c_distribution")

# Row 4 - source vs target + weekday
left, right = st.columns(2)
with left, st.container(border=True):
    show(charts.source_target_chart(analytics.source_vs_target(df)), "c_src_tgt")
with right, st.container(border=True):
    show(charts.weekday_chart(analytics.weekday_counts(df)), "c_weekday")

# Row 5 - recent activity
st.subheader("Recent translations")
recent = db.get_history(limit=5)
if not recent:
    empty_state("Nothing here yet", "Your five most recent translations will appear here.")
else:
    for row in recent:
        with st.container(border=True):
            st.caption(f"{row['timestamp']}  ·  {row['source_language']} → {row['target_language']}")
            c1, c2 = st.columns(2)
            c1.write(row["original_text"][:200] + ("…" if len(row["original_text"]) > 200 else ""))
            c2.write(row["translated_text"][:200] + ("…" if len(row["translated_text"]) > 200 else ""))

if not df.empty:
    with st.expander("View chart data as a table"):
        st.dataframe(
            analytics.language_counts(df).rename(columns={"language": "Target language", "translations": "Translations"}),
            hide_index=True, use_container_width=True,
        )

render_footer()
