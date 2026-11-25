"""Sign-in / sign-up / guest screen and session helpers."""
from __future__ import annotations

import sqlite3
import time

import streamlit as st

from components.sidebar import page_header
from database.db_manager import GUEST_LIFETIME_HOURS, ScopedDB, get_db

HIDE_SIDEBAR = """
<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display: none; }
</style>
"""


def is_logged_in() -> bool:
    return bool(st.session_state.get("user"))


def current_user() -> dict:
    return st.session_state["user"]


def current_db() -> ScopedDB:
    """The database bound to the signed-in user (history/favorites are per-user)."""
    return ScopedDB(get_db(), current_user()["id"])


def logout() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def _login(user: dict) -> None:
    st.session_state["user"] = user
    st.rerun()


def render_login() -> None:
    """Full-page sign-in screen. Call ``st.stop()`` afterwards."""
    st.markdown(HIDE_SIDEBAR, unsafe_allow_html=True)
    page_header(
        "Welcome to LinguaAI 👋",
        "Sign in to keep your translation history, or try the app right away as a guest.",
        chips=["🌍 19 languages", "📄 Documents", "🔊 Text-to-speech", "📊 Personal analytics"],
    )
    _, centre, _ = st.columns([1, 2, 1])
    with centre:
        tab_in, tab_up, tab_guest = st.tabs(["Sign in", "Create account", "Guest"])
        db = get_db()

        with tab_in, st.form("signin_form"):
            username = st.text_input("Username", key="si_user")
            password = st.text_input("Password", type="password", key="si_pass")
            if st.form_submit_button("Sign in", type="primary", use_container_width=True):
                try:
                    user = db.authenticate(username, password)
                except sqlite3.Error as exc:
                    st.error(f"The database is unavailable: {exc}")
                else:
                    if user:
                        _login(user)
                    time.sleep(0.4)  # slows down password guessing
                    st.error("Incorrect username or password.")

        with tab_up, st.form("signup_form"):
            username = st.text_input("Choose a username", key="su_user", help="3-30 letters, numbers, . - _")
            password = st.text_input("Choose a password", type="password", key="su_pass", help="At least 6 characters")
            confirm = st.text_input("Repeat password", type="password", key="su_pass2")
            if st.form_submit_button("Create account", type="primary", use_container_width=True):
                if password != confirm:
                    st.error("The two passwords do not match.")
                else:
                    try:
                        _login(db.create_user(username, password))
                    except ValueError as exc:
                        st.error(str(exc))
                    except sqlite3.Error as exc:
                        st.error(f"The database is unavailable: {exc}")

        with tab_guest:
            st.write(
                "Explore everything without an account. Guest history is private to this session and "
                f"is **deleted automatically after {GUEST_LIFETIME_HOURS} hours**."
            )
            if st.button("Continue as guest", use_container_width=True, key="guest_btn"):
                try:
                    _login(db.create_guest())
                except sqlite3.Error as exc:
                    st.error(f"The database is unavailable: {exc}")

        st.caption("Passwords are stored only as salted hashes. There is no password recovery - keep yours safe.")


def render_account_box() -> None:
    """Sidebar block: who is signed in, plus the log-out button."""
    user = current_user()
    with st.sidebar:
        icon = "👤" if user["is_guest"] else "✅"
        st.markdown(f"{icon} **{user['username']}**")
        if user["is_guest"]:
            st.caption(f"Guest session - data is deleted after {GUEST_LIFETIME_HOURS} h.")
        if st.button("Log out", key="logout_btn", use_container_width=True):
            logout()
            st.rerun()
