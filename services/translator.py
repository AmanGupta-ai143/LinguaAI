"""Translation service.

``TranslationService`` is the only class the UI talks to. It validates input,
splits long text into API-sized chunks and delegates the actual translation to a
*provider*. ``MyMemoryProvider`` is the provider used today; to add Google Cloud
Translation or Microsoft Translator, subclass ``BaseProvider`` and implement
``translate_chunk`` - no UI code has to change.
"""
from __future__ import annotations

import html
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional

import requests

from services.language_detector import detect_language

# --------------------------------------------------------------------------- languages
AUTO_DETECT = "Auto-detect"

# display name -> ISO code understood by MyMemory and gTTS
LANGUAGES: dict[str, str] = {
    "English": "en",
    "Hindi": "hi",
    "Bengali": "bn",
    "Marathi": "mr",
    "Tamil": "ta",
    "Telugu": "te",
    "Urdu": "ur",
    "French": "fr",
    "Spanish": "es",
    "German": "de",
    "Italian": "it",
    "Portuguese": "pt",
    "Dutch": "nl",
    "Russian": "ru",
    "Turkish": "tr",
    "Arabic": "ar",
    "Japanese": "ja",
    "Korean": "ko",
    "Chinese (Simplified)": "zh-CN",
}
CODE_TO_NAME = {code: name for name, code in LANGUAGES.items()}

# --------------------------------------------------------------------------- limits
MAX_INPUT_CHARS = 5000          # per translation in the Translator page
MAX_CHUNK_BYTES = 450           # MyMemory accepts at most 500 bytes per request
REQUEST_TIMEOUT = (5, 15)       # (connect, read) seconds
MYMEMORY_URL = "https://api.mymemory.translated.net/get"


# --------------------------------------------------------------------------- errors
class TranslationError(Exception):
    """Base class; the message is safe to show to end users."""


class ValidationError(TranslationError):
    """The input was rejected before any API call was made."""


class APIError(TranslationError):
    """The translation provider returned an error or an unusable response."""


class APITimeoutError(APIError):
    """The provider did not answer in time."""


class QuotaExceededError(APIError):
    """The provider's usage limit has been reached."""


# --------------------------------------------------------------------------- helpers
@dataclass
class TranslationResult:
    translated_text: str
    source_code: str
    target_code: str
    detected_code: Optional[str]
    provider: str
    chunks: int

    @property
    def detected_name(self) -> Optional[str]:
        return CODE_TO_NAME.get(self.detected_code) if self.detected_code else None


def _byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def _hard_split(text: str, max_bytes: int) -> list[str]:
    """Split a single over-long token by characters, respecting the byte limit."""
    parts, current = [], ""
    for ch in text:
        if _byte_len(current + ch) > max_bytes:
            parts.append(current)
            current = ch
        else:
            current += ch
    if current:
        parts.append(current)
    return parts


def split_into_chunks(text: str, max_bytes: int = MAX_CHUNK_BYTES) -> list[str]:
    """Split ``text`` into pieces of at most ``max_bytes`` UTF-8 bytes.

    Splits at sentence boundaries first, then at words, then (as a last resort)
    at characters, so that no chunk exceeds the provider's request limit.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?।。！？])\s+", text)
    pieces: list[str] = []
    for sentence in sentences:
        if _byte_len(sentence) <= max_bytes:
            pieces.append(sentence)
            continue
        current = ""
        for word in sentence.split(" "):
            if _byte_len(word) > max_bytes:
                if current:
                    pieces.append(current)
                    current = ""
                pieces.extend(_hard_split(word, max_bytes))
                continue
            candidate = f"{current} {word}".strip()
            if _byte_len(candidate) > max_bytes:
                pieces.append(current)
                current = word
            else:
                current = candidate
        if current:
            pieces.append(current)

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current} {piece}".strip()
        if current and _byte_len(candidate) > max_bytes:
            chunks.append(current)
            current = piece
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def swap_languages(source: str, target: str, detected: Optional[str] = None) -> tuple[str, str]:
    """Return ``(new_source, new_target)`` for the swap button.

    If the source is "Auto-detect" the detected language (if known) becomes the new
    target; otherwise swapping is impossible and ``ValueError`` is raised.
    """
    if source == AUTO_DETECT:
        if not detected:
            raise ValueError("Choose a source language (or translate once so it can be detected) before swapping.")
        source = detected
    return target, source


def language_code(name: str) -> str:
    try:
        return LANGUAGES[name]
    except KeyError:
        raise ValidationError(f"Unsupported language: {name!r}.") from None


# --------------------------------------------------------------------------- providers
class BaseProvider(ABC):
    """Interface every translation backend must implement."""

    name = "base"

    @abstractmethod
    def translate_chunk(self, text: str, source_code: str, target_code: str) -> tuple[str, Optional[str]]:
        """Translate one chunk. Returns ``(translated_text, detected_code_or_None)``.

        ``source_code`` may be ``"auto"``. Must raise ``APIError`` subclasses on failure.
        """


class MyMemoryProvider(BaseProvider):
    """Provider for the free MyMemory Translation API (https://mymemory.translated.net).

    The optional environment variable ``MYMEMORY_EMAIL`` is sent as the ``de``
    parameter, which MyMemory documents as raising the daily free quota.
    """

    name = "MyMemory"

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        email: Optional[str] = None,
        timeout=REQUEST_TIMEOUT,
        retries: int = 1,
        retry_delay: float = 1.0,
    ):
        self.session = session or requests.Session()
        self.email = email if email is not None else os.environ.get("MYMEMORY_EMAIL")
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay

    def _get(self, params: dict) -> requests.Response:
        attempt = 0
        while True:
            try:
                return self.session.get(MYMEMORY_URL, params=params, timeout=self.timeout)
            except requests.Timeout as exc:
                if attempt >= self.retries:
                    raise APITimeoutError(
                        "The translation service took too long to respond. Please try again."
                    ) from exc
            except requests.ConnectionError as exc:
                if attempt >= self.retries:
                    raise APIError(
                        "Could not reach the translation service. Check your internet connection."
                    ) from exc
            except requests.RequestException as exc:
                raise APIError(f"Translation request failed: {exc}") from exc
            attempt += 1
            time.sleep(self.retry_delay)

    def translate_chunk(self, text: str, source_code: str, target_code: str) -> tuple[str, Optional[str]]:
        source = "Autodetect" if source_code == "auto" else source_code
        params = {"q": text, "langpair": f"{source}|{target_code}"}
        if self.email:
            params["de"] = self.email

        response = self._get(params)
        if response.status_code == 429:
            raise QuotaExceededError("The daily translation limit has been reached. Try again later.")
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise APIError(f"The translation service returned HTTP {response.status_code}.") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise APIError("The translation service returned an unreadable response.") from exc

        try:
            status = int(data.get("responseStatus", 0))
        except (TypeError, ValueError):
            status = 0
        payload = data.get("responseData") or {}
        translated = payload.get("translatedText")
        details = str(data.get("responseDetails") or "").strip()

        upper = (translated or "").upper()
        if status == 429 or "MYMEMORY WARNING" in upper or "QUOTA" in details.upper():
            raise QuotaExceededError(
                "The free daily translation limit has been reached. Try again tomorrow, "
                "or set MYMEMORY_EMAIL to raise the limit."
            )
        if status != 200 or not translated:
            raise APIError(f"Translation failed: {details or 'unknown error from the service'}.")

        detected = payload.get("detectedLanguage")
        detected = detected if isinstance(detected, str) and detected else None
        return html.unescape(translated), detected


# --------------------------------------------------------------------------- service
class TranslationService:
    """Validates input, chunks text and calls the configured provider."""

    def __init__(self, provider: Optional[BaseProvider] = None):
        self.provider = provider or MyMemoryProvider()

    @staticmethod
    def validate_text(text: Optional[str], max_chars: int = MAX_INPUT_CHARS) -> str:
        if text is None or not text.strip():
            raise ValidationError("Please enter some text to translate.")
        cleaned = text.strip()
        if len(cleaned) > max_chars:
            raise ValidationError(
                f"Text is too long ({len(cleaned):,} characters). The limit is {max_chars:,}."
            )
        return cleaned

    def translate(
        self,
        text: str,
        source: str,
        target: str,
        max_chars: int = MAX_INPUT_CHARS,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> TranslationResult:
        """Translate ``text`` from ``source`` to ``target`` (language *names*)."""
        text = self.validate_text(text, max_chars)
        if target not in LANGUAGES:
            raise ValidationError("Please choose a valid target language.")
        target_code = LANGUAGES[target]

        detected_code: Optional[str] = None
        if source == AUTO_DETECT:
            detected_code = detect_language(text)
            source_code = detected_code or "auto"
        elif source in LANGUAGES:
            source_code = LANGUAGES[source]
        else:
            raise ValidationError("Please choose a valid source language.")
        if source_code == target_code:
            raise ValidationError("Source and target languages are the same. Pick a different target language.")

        paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
        plan = [split_into_chunks(p) for p in paragraphs]
        total = sum(len(chunks) for chunks in plan)

        done = 0
        translated_paragraphs: list[str] = []
        for chunks in plan:
            parts = []
            for chunk in chunks:
                translated, detected = self.provider.translate_chunk(chunk, source_code, target_code)
                if detected_code is None and detected:
                    detected_code = detected.split("-")[0] if detected.split("-")[0] in CODE_TO_NAME else detected
                parts.append(translated)
                done += 1
                if progress_callback:
                    progress_callback(done, total)
            translated_paragraphs.append(" ".join(parts))

        return TranslationResult(
            translated_text="\n\n".join(translated_paragraphs),
            source_code=source_code,
            target_code=target_code,
            detected_code=detected_code,
            provider=self.provider.name,
            chunks=total,
        )


_service: Optional[TranslationService] = None


def get_service() -> TranslationService:
    global _service
    if _service is None:
        _service = TranslationService()
    return _service
