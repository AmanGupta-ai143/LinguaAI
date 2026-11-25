"""Document translation (TXT, PDF, DOCX)."""
import sqlite3

import streamlit as st

from components.sidebar import page_header
from components.translator_ui import source_options, target_options, text_panel
from components.auth import current_db
from services.document_handler import (
    ALLOWED_EXTENSIONS, MAX_DOCUMENT_CHARS, MAX_FILE_BYTES, DocumentError, extract_text, format_size,
)
from services.translator import AUTO_DETECT, TranslationError, get_service

page_header("Document translation", "Upload a TXT, PDF or DOCX file and translate its text.")
st.caption(
    f"Supported: {', '.join(sorted(e.upper().strip('.') for e in ALLOWED_EXTENSIONS))} · "
    f"max {format_size(MAX_FILE_BYTES)} · up to {MAX_DOCUMENT_CHARS:,} characters · text only (no OCR)."
)

c1, c2 = st.columns(2)
src = c1.selectbox("From", source_options(), key="doc_src")
tgt = c2.selectbox("To", target_options(), index=target_options().index("English"), key="doc_tgt")

# type=None so that unsupported files reach our own validation and get a clear message.
upload = st.file_uploader("Choose a document", key="doc_upload")

if upload is not None:
    data = upload.getvalue()
    st.write(f"**{upload.name}** · {format_size(len(data))}")
    try:
        text = extract_text(upload.name, data)
    except DocumentError as exc:
        st.error(str(exc))
        st.stop()

    st.success(f"Extracted {len(text):,} characters.")
    with st.expander("Preview extracted text"):
        st.text(text[:3000] + ("\n…" if len(text) > 3000 else ""))

    if st.button("Translate document", type="primary"):
        bar = st.progress(0.0, text="Translating...")
        try:
            result = get_service().translate(
                text, src, tgt, max_chars=MAX_DOCUMENT_CHARS,
                progress_callback=lambda done, total: bar.progress(done / total, text=f"Translating part {done} of {total}..."),
            )
        except TranslationError as exc:
            bar.empty()
            st.error(str(exc))
        else:
            bar.empty()
            src_name = src if src != AUTO_DETECT else (result.detected_name or AUTO_DETECT)
            st.session_state["doc_result"] = {
                "name": upload.name, "original": text, "translated": result.translated_text,
                "source": src_name, "target": tgt, "chunks": result.chunks,
            }
            try:
                current_db().add_translation(text, result.translated_text, src_name, tgt, character_count=len(text))
            except sqlite3.Error as exc:
                st.warning(f"Translated, but could not be saved to history: {exc}")

doc = st.session_state.get("doc_result")
if doc and upload is not None and doc["name"] == upload.name:
    st.divider()
    st.caption(f"Translated {doc['source']} → {doc['target']} in {doc['chunks']} request(s).")
    left, right = st.columns(2)
    with left:
        text_panel("Original", doc["original"][:3000] + (" …" if len(doc["original"]) > 3000 else ""))
    with right:
        text_panel("Translation", doc["translated"][:3000] + (" …" if len(doc["translated"]) > 3000 else ""))
    stem = doc["name"].rsplit(".", 1)[0]
    st.download_button(
        "⬇️ Download translated text (.txt)", data=doc["translated"].encode("utf-8"),
        file_name=f"{stem}_{doc['target'].split()[0].lower()}.txt", mime="text/plain; charset=utf-8",
    )
