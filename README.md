# 🌐 LinguaAI – Smart Language Translation Platform

A multilingual translation web app built with **Python + Streamlit**, using the **MyMemory Translation API**.
Translate text and documents, listen to the result, save favorites, and explore your usage on an interactive dashboard.

## Problem statement
People regularly need quick, reliable translations of short texts and documents. This project builds a practical tool that
takes text in one language, sends it to a real translation API, and returns the translation – with the surrounding features
(history, favorites, speech, analytics) that make it feel like a real product.

## Objectives
- Integrate a real translation API (no fake or hard-coded translations)
- Demonstrate Python, API handling, basic NLP (language detection, text chunking), data processing and visualization
- Keep the code modular, validated, tested and easy to extend

## Features
| Area | What it does |
|---|---|
| **Translator** | 19 languages, auto-detect, swap, character counter, copy, clear, loading spinner |
| **Documents** | TXT / PDF / DOCX upload, text extraction, chunked translation with progress bar, download |
| **Text-to-speech** | Listen to original and translated text (gTTS), graceful message for unsupported cases |
| **Accounts** | Sign up / sign in (salted password hashes) or continue as a guest; every user sees only their own data |
| **Theme** | Dark-mode toggle at the top of every page (per visitor) |
| **Search** | Search box on every page + a results page covering history and favorites |
| **History** | Database-backed list with search, pagination, reuse, delete, clear-all |
| **Favorites** | Save / search / reuse / remove |
| **Dashboard** | KPI cards + 5 Plotly charts, all computed from stored history; empty states when there is no data |
| **Robustness** | Input & file validation, size limits, timeouts + one retry, friendly errors for quota / network / bad responses |

### Dashboard charts (all from real records)
1. Translation activity over time – line chart (daily / weekly / monthly)
2. Most used target languages – horizontal bar
3. Language distribution – donut
4. KPI cards – translations, characters, languages used, favorites
5. Source vs target languages – grouped bar
6. Usage by weekday – bar

Chart colours come from a colour-blind-safe palette that was validated for both light and dark themes.

## Technologies
Python 3.10+ · Streamlit · Requests · Pandas · Plotly · gTTS · SQLite (local) / Turso libSQL (optional hosted database) · pypdf · python-docx · pytest

## System architecture
```mermaid
flowchart LR
  subgraph Frontend [Streamlit UI]
    P[pages/*] --> C[components/*]
  end
  subgraph Backend [services/]
    T[translator.py<br/>validation + chunking]
    L[language_detector.py]
    S[speech.py]
    D[document_handler.py]
    A[analytics.py]
  end
  subgraph Ext [External services]
    M[(MyMemory API)]
    G[(gTTS)]
  end
  DB[(SQLite or hosted libSQL<br/>database/db_manager.py)]
  P --> T & S & D & A
  T --> L
  T --> M
  S --> G
  P --> DB
  A --> DB
```

`TranslationService` talks to a `BaseProvider`; `MyMemoryProvider` is the current implementation. To add Google Cloud
Translation or Microsoft Translator, subclass `BaseProvider` and implement `translate_chunk` – the UI needs no changes.

## Application workflow
```mermaid
flowchart TD
  A[Choose languages + enter text] --> B{Valid input?}
  B -- no --> E[Show friendly error]
  B -- yes --> C[Split into ≤450-byte chunks]
  C --> D[MyMemory API request per chunk<br/>timeout + retry]
  D -- error --> E
  D -- ok --> F[Combine chunks]
  F --> G[Display translation]
  F --> H[(Save to SQLite history)]
  H --> I[Dashboard KPIs + charts read from history]
  G --> J[Copy · Listen · Favorite]
```

Document translation adds *upload → validate → extract text* in front of the same pipeline and a download step at the end.

## Database structure
```
users(id PK, username UNIQUE, password_hash, salt, created_at, is_guest)
translation_history(id PK, original_text, translated_text, source_language,
                    target_language, timestamp, character_count, user_id)
favorites(id PK, original_text, translated_text, source_language,
          target_language, created_at, user_id)
```
Locally the file is created automatically at `data/linguaai.db` (git-ignored). Older databases are migrated automatically.

## Installation
```bash
git clone https://github.com/<your-username>/LinguaAI.git
cd LinguaAI
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run
```bash
streamlit run app.py
```
Open http://localhost:8501. Switch light/dark theme from **⋮ → Settings → Theme**.

Run the tests:
```bash
pytest -v
```

Optional configuration (see `.env.example`, or Streamlit *Secrets* when deployed):

| Variable | Purpose |
|---|---|
| `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` | Use a hosted database so history survives restarts (see below) |
| `LINGUAAI_TZ` | Time zone for timestamps and "today", e.g. `Asia/Kolkata` (default: server time) |
| `MYMEMORY_EMAIL` | Raises MyMemory's free daily quota |
| `LINGUAAI_DB_PATH` | Moves the local SQLite file |

No API key is required to run the app, and no secrets are stored in the repository.

## Deploying on Streamlit Community Cloud (with persistent history)
Streamlit Cloud's disk is wiped on every restart, so use a free hosted database for history, favorites and accounts:

1. Create a free database at [turso.tech](https://turso.tech) and copy its **URL** (`libsql://…`) and a **database token**.
2. In Streamlit Cloud open **Manage app → Settings → Secrets** and add:
   ```toml
   TURSO_DATABASE_URL = "libsql://your-db-your-org.turso.io"
   TURSO_AUTH_TOKEN = "your-token"
   LINGUAAI_TZ = "Asia/Kolkata"
   ```
3. Reboot the app. Tables are created automatically.

Without these secrets the app still works, but data lives in temporary local storage. If the hosted database is unreachable the app falls back to local storage and shows a warning. The hosted-database client (`database/remote.py`) uses Turso's documented HTTP API with plain `requests`.

## Screenshots
Add your own after running the app (save into `docs/screenshots/`) and reference them here, e.g.:

```markdown
![Dashboard](docs/screenshots/dashboard.png)
![Translator](docs/screenshots/translator.png)
```

## API documentation
**MyMemory** – `GET https://api.mymemory.translated.net/get`

| Parameter | Meaning |
|---|---|
| `q` | text to translate (≤ 500 bytes per request – LinguaAI chunks at 450) |
| `langpair` | `source\|target`, e.g. `en\|hi` (`Autodetect\|hi` for auto-detection) |
| `de` | optional email, raises the free daily quota |

Response: JSON with `responseData.translatedText`, `responseStatus` (200 = OK) and `responseDetails`.
LinguaAI treats non-200 statuses and MyMemory's quota warning text as errors rather than showing them as translations.

Internal API (`services/translator.py`): `TranslationService.translate(text, source, target) -> TranslationResult`,
raising `ValidationError`, `APIError`, `APITimeoutError` or `QuotaExceededError`.

## Limitations
- MyMemory's free tier has a daily quota and its quality is lower than commercial engines, especially for long or technical text.
- Auto-detection is a lightweight offline heuristic (script analysis + stop-words); the API's own detection is the fallback.
- Scanned (image-only) PDFs are not supported (no OCR). Document limit: 5 MB / 20,000 characters.
- Persistence on Streamlit Community Cloud needs the hosted-database secrets above; otherwise data is lost on restart.
- Accounts are deliberately simple: username + password, no e-mail verification and **no password recovery**. Guest data is deleted after 24 hours.
- The 🌙 Dark mode toggle at the top of each page is a per-visitor visual switch (Streamlit has no supported per-user theme API, so the page is colour-inverted with deliberate colours restored); Streamlit's own ⋮ → Settings → Theme also works.
- Text-to-speech needs internet access (gTTS calls Google's service).

## Future enhancements
Google Cloud / Microsoft Translator providers · e-mail verification and password reset · OCR for scanned PDFs ·
translated DOCX/PDF export · translation memory & glossary.

## Project structure
```
app.py                 entry point (navigation, styling)
pages/                 Home, Translator, Documents, History, Favorites, About, Search
services/              translator, language_detector, speech, document_handler, analytics, auth
database/              schema.py, db_manager.py, remote.py (hosted-DB client)
components/            sidebar, auth, dashboard_cards, charts, translator_ui
assets/                logo.png, styles.css
tests/                 pytest suite
```
