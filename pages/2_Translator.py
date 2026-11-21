"""Translation workspace."""
import sqlite3

import streamlit as st

from components.sidebar import page_header
from components.translator_ui import (
    audio_controls, copy_button, save_favorite_button, source_options, target_options, text_panel,
)
from database.db_manager import get_db
from services.translator import (
    AUTO_DETECT, LANGUAGES, MAX_INPUT_CHARS, TranslationError, get_service, swap_languages,
)

ss = st.session_state
ss.setdefault("tr_src", AUTO_DETECT)
ss.setdefault("tr_tgt", "Hindi")
ss.setdefault("tr_text", "")

# A stored translation sent here from History / Favorites.
if "prefill" in ss:
    pre = ss.pop("prefill")
    ss["tr_text"] = pre["original"][:MAX_INPUT_CHARS]   # stored document texts can be longer
    ss["tr_src"] = pre["source"] if pre["source"] in LANGUAGES else AUTO_DETECT
    ss["tr_tgt"] = pre["target"] if pre["target"] in LANGUAGES else "Hindi"
    ss["tr_result"] = {
        "original": pre["original"], "translated": pre["translated"],
        "source": pre["source"], "target": pre["target"],
        "source_code": LANGUAGES.get(pre["source"]), "target_code": LANGUAGES.get(pre["target"]),
        "saved": False,
    }
    ss.pop("audio_cache", None)


def on_swap():
    result = ss.get("tr_result")
    detected = result["source"] if result and result["source"] in LANGUAGES else None
    try:
        new_src, new_tgt = swap_languages(ss["tr_src"], ss["tr_tgt"], detected)
    except ValueError as exc:
        ss["tr_notice"] = str(exc)
        return
    ss["tr_src"], ss["tr_tgt"] = new_src, new_tgt
    if result:                      # like Google Translate: the output becomes the new input
        ss["tr_text"] = result["translated"]
        ss.pop("tr_result", None)


def on_clear():
    ss["tr_text"] = ""
    ss.pop("tr_result", None)
    ss.pop("audio_cache", None)


page_header("Translator", "Type or paste text, choose languages and translate.")

c_src, c_swap, c_tgt = st.columns([5, 1, 5])
c_src.selectbox("From", source_options(), key="tr_src")
c_swap.write("")
c_swap.button("⇄", on_click=on_swap, help="Swap languages", use_container_width=True)
c_tgt.selectbox("To", target_options(), key="tr_tgt")
if "tr_notice" in ss:
    st.info(ss.pop("tr_notice"))

st.text_area(
    "Text to translate", key="tr_text", height=180, max_chars=MAX_INPUT_CHARS,
    placeholder="Enter text here...",
)
length = len(ss["tr_text"])
st.caption(f"{length:,} / {MAX_INPUT_CHARS:,} characters")

b1, b2, _ = st.columns([2, 1, 4])
translate_clicked = b1.button("Translate", type="primary", use_container_width=True)
b2.button("Clear", on_click=on_clear, use_container_width=True)

if translate_clicked:
    try:
        with st.spinner("Translating..."):
            res = get_service().translate(ss["tr_text"], ss["tr_src"], ss["tr_tgt"])
    except TranslationError as exc:
        st.error(str(exc))
    else:
        src_name = ss["tr_src"] if ss["tr_src"] != AUTO_DETECT else (res.detected_name or AUTO_DETECT)
        ss["tr_result"] = {
            "original": ss["tr_text"].strip(), "translated": res.translated_text,
            "source": src_name, "target": ss["tr_tgt"],
            "source_code": res.source_code if res.source_code != "auto" else res.detected_code,
            "target_code": res.target_code, "saved": False,
        }
        ss.pop("audio_cache", None)
        try:
            get_db().add_translation(ss["tr_result"]["original"], res.translated_text, src_name, ss["tr_tgt"])
        except sqlite3.Error as exc:
            st.warning(f"Translation done, but it could not be saved to history: {exc}")

result = ss.get("tr_result")
if result:
    st.divider()
    if ss["tr_src"] == AUTO_DETECT and result["source"] != AUTO_DETECT:
        st.caption(f"Detected source language: **{result['source']}**")
    left, right = st.columns(2)
    with left:
        text_panel(f"Original · {result['source']}", result["original"])
        st.caption(f"{len(result['original']):,} characters")
    with right:
        text_panel(f"Translation · {result['target']}", result["translated"])
        st.caption(f"{len(result['translated']):,} characters")

    a1, a2, _ = st.columns([1, 2, 3])
    with a1:
        copy_button(result["translated"])
    with a2:
        save_favorite_button(result["original"], result["translated"], result["source"], result["target"], "tr_fav")
    st.write("")
    audio_controls("tr", result["original"], result["source_code"], result["translated"], result["target_code"])
