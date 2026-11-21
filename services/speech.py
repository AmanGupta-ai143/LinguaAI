"""Text-to-speech using gTTS (Google Text-to-Speech).

gTTS is imported lazily so the rest of the app (and the test-suite) keeps working
even if the package is missing. Audio is returned as MP3 bytes for ``st.audio``.
"""
from __future__ import annotations

import io

MAX_TTS_CHARS = 3000

# Codes gTTS supports for the languages offered in the app.
SUPPORTED_TTS = {"en", "hi", "bn", "mr", "ta", "te", "ur", "fr", "es", "de", "it", "pt",
                 "nl", "ru", "tr", "ar", "ja", "ko", "zh-CN"}


class SpeechError(Exception):
    """Raised with a user-friendly message when audio cannot be generated."""


def is_supported(language_code: str) -> bool:
    return language_code in SUPPORTED_TTS


def synthesize(text: str, language_code: str) -> bytes:
    """Return MP3 audio bytes for ``text`` spoken in ``language_code``."""
    if not text or not text.strip():
        raise SpeechError("There is no text to read aloud.")
    if not is_supported(language_code):
        raise SpeechError(f"Text-to-speech is not available for language code '{language_code}'.")
    if len(text) > MAX_TTS_CHARS:
        raise SpeechError(f"Text is too long for audio ({len(text):,} characters; limit {MAX_TTS_CHARS:,}).")
    try:
        from gtts import gTTS
    except ImportError as exc:
        raise SpeechError("The gTTS package is not installed. Run: pip install gTTS") from exc
    try:
        buffer = io.BytesIO()
        gTTS(text=text.strip(), lang=language_code).write_to_fp(buffer)
        return buffer.getvalue()
    except Exception as exc:  # gTTS raises several error types (network, bad language, ...)
        raise SpeechError(
            "Could not generate audio. The speech service may be unreachable - please try again."
        ) from exc
