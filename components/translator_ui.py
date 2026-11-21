"""Reusable UI pieces for translation screens."""
from __future__ import annotations

import html
import json
import sqlite3
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components

from database.db_manager import get_db
from services import speech
from services.translator import AUTO_DETECT, CODE_TO_NAME, LANGUAGES


def source_options() -> list[str]:
    return [AUTO_DETECT, *LANGUAGES.keys()]


def target_options() -> list[str]:
    return list(LANGUAGES.keys())


def text_panel(label: str, text: str) -> None:
    """Read-only text block (HTML-escaped)."""
    st.markdown(
        f'<div class="lg-label">{html.escape(label)}</div><div class="lg-text">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def copy_button(text: str, label: str = "📋 Copy") -> None:
    """Browser-side copy-to-clipboard button (works with a fallback for older browsers)."""
    payload = json.dumps(text).replace("</", "<\\/")
    components.html(
        f"""
        <button id="b" style="font:600 14px system-ui,sans-serif;padding:7px 14px;border-radius:10px;
          border:1px solid rgba(127,127,127,.45);background:transparent;color:inherit;cursor:pointer;">
          {html.escape(label)}</button>
        <script>
          const text = {payload};
          const b = document.getElementById('b');
          b.onclick = async () => {{
            try {{ await navigator.clipboard.writeText(text); }}
            catch (e) {{
              const t = document.createElement('textarea'); t.value = text;
              document.body.appendChild(t); t.select(); document.execCommand('copy'); t.remove();
            }}
            b.textContent = '✅ Copied'; setTimeout(() => b.textContent = {json.dumps(label)}, 1500);
          }};
        </script>
        """,
        height=46,
    )


def audio_controls(key: str, original: str, original_code: Optional[str], translated: str, target_code: str) -> None:
    """Two 'listen' buttons plus audio players. Audio is cached in session state."""
    cache = st.session_state.setdefault("audio_cache", {})
    cols = st.columns(2)
    for col, which, text, code in (
        (cols[0], "original", original, original_code),
        (cols[1], "translated", translated, target_code),
    ):
        with col:
            if st.button(f"🔊 Listen to {which}", key=f"{key}_tts_{which}", use_container_width=True):
                if not code:
                    cache[(key, which)] = ("error", "The original language could not be detected, so audio is unavailable.")
                else:
                    try:
                        with st.spinner("Generating audio..."):
                            cache[(key, which)] = ("ok", speech.synthesize(text, code))
                    except speech.SpeechError as exc:
                        cache[(key, which)] = ("error", str(exc))
            entry = cache.get((key, which))
            if entry:
                kind, value = entry
                if kind == "ok":
                    st.audio(value, format="audio/mp3")
                else:
                    st.warning(value)


def save_favorite_button(original: str, translated: str, source: str, target: str, key: str) -> None:
    if st.button("⭐ Save to favorites", key=key, use_container_width=True):
        try:
            _, created = get_db().add_favorite(original, translated, source, target)
            st.toast("Saved to favorites" if created else "Already in your favorites", icon="⭐")
        except (sqlite3.Error, ValueError) as exc:
            st.error(f"Could not save favorite: {exc}")


def reuse_in_translator(original: str, translated: str, source: str, target: str) -> None:
    """Hand a stored translation to the Translator page and open it."""
    st.session_state["prefill"] = {
        "original": original, "translated": translated, "source": source, "target": target,
    }
    st.switch_page("pages/2_Translator.py")


def code_to_name(code: Optional[str]) -> Optional[str]:
    return CODE_TO_NAME.get(code) if code else None
