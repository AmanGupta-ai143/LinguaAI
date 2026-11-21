# Testing

## Automated (`pytest`)

```bash
pytest -v
```

The suite never touches the network: the HTTP session and gTTS are mocked.

| Requirement | Covered by |
|---|---|
| English → Hindi, Hindi → English, English → French | `test_translation_pairs` |
| Language swapping (incl. with auto-detect) | `test_swap_*` |
| Automatic language detection | `test_language_detection`, `test_auto_detect_*` |
| Empty input validation | `test_empty_input_is_rejected_without_api_call` |
| Long text processing / chunking | `test_chunks_*`, `test_long_text_is_translated_in_multiple_requests_and_reported` |
| API failure handling (timeout, 429, 5xx, bad JSON, quota text) | `test_timeout_*`, `test_http_*`, `test_quota_*`, `test_malformed_json_*` |
| Text-to-speech guard rails | `test_tts_*` |
| Translation history (CRUD, search, pagination) | `tests/test_database.py` |
| Favorites (CRUD, duplicates, search) | `test_favorites_*` |
| Document upload & extraction (TXT/PDF/DOCX, bad files, size limits) | `tests/test_documents_and_speech.py` |
| Dashboard numbers & chart data reflect real records | `test_stats_*`, `test_*_activity`, `test_language_counts_*`, … |

## Manual checklist (needs internet + `streamlit run app.py`)

These need a real browser, the live MyMemory API or Google's TTS service, so they are checked by hand:

- [ ] Translate "Hello, how are you?" English → Hindi, Hindi → English, English → French; result appears and a history row is created
- [ ] Auto-detect: paste French text with *From = Auto-detect*; detected language is shown
- [ ] ⇄ swaps languages and moves the translation into the input box
- [ ] 📋 Copy puts the translation on the clipboard
- [ ] 🔊 Listen to original / translated plays audio; an unsupported language shows a friendly message
- [ ] Turn off Wi-Fi and translate → readable error, no crash
- [ ] ⭐ Save to favorites → Favorites page shows it; Home KPI "Favorite translations" increments
- [ ] Upload a TXT, a PDF and a DOCX → text extracted → translate → download works; upload a `.exe` → clear error
- [ ] After a few translations the Home charts update (refresh the Home page) and show the same counts as History
- [ ] Toggle light/dark theme (⋮ → Settings → Theme) and check the charts remain readable
