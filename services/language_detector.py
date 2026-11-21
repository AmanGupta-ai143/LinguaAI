"""Lightweight, offline language detection.

Detection works in two steps:
  1. Unicode script analysis - reliable for non-Latin scripts (Devanagari, Arabic,
     Cyrillic, CJK, Hangul, Tamil, ...).
  2. Stop-word voting for Latin-script languages (English, French, Spanish, ...).

This is a heuristic, not a statistical model. When it is not confident it returns
``None`` and the translation service falls back to the API's own auto-detection.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Optional

# (start, end, bucket) code-point ranges
_SCRIPT_RANGES = [
    (0x0900, 0x097F, "devanagari"),
    (0x0980, 0x09FF, "bengali"),
    (0x0B80, 0x0BFF, "tamil"),
    (0x0C00, 0x0C7F, "telugu"),
    (0x0600, 0x06FF, "arabic"),
    (0x0750, 0x077F, "arabic"),
    (0x0400, 0x04FF, "cyrillic"),
    (0x3040, 0x309F, "kana"),
    (0x30A0, 0x30FF, "kana"),
    (0xAC00, 0xD7AF, "hangul"),
    (0x1100, 0x11FF, "hangul"),
    (0x4E00, 0x9FFF, "han"),
]

_URDU_LETTERS = set("ٹڈڑںےھگچپژکۂۃ")
_HINDI_MARKERS = {"है", "हैं", "और", "नहीं", "क्या", "में", "से", "को", "का", "की", "के", "था", "मैं", "आप", "यह", "तुम"}
_MARATHI_MARKERS = {"आहे", "आणि", "नाही", "काय", "मी", "तू", "आपण", "होते", "ला", "चा", "ची", "चे", "हा", "ही"}

_STOPWORDS = {
    "en": {"the", "and", "is", "are", "you", "to", "of", "in", "that", "it", "for", "with", "this", "what", "how", "hello", "thanks", "my", "name", "i", "have"},
    "fr": {"le", "la", "les", "et", "est", "un", "une", "des", "je", "vous", "nous", "pour", "que", "bonjour", "merci", "dans", "pas", "avec", "suis", "ce", "mon"},
    "es": {"el", "la", "los", "las", "y", "es", "un", "una", "que", "de", "por", "para", "hola", "gracias", "con", "no", "estoy", "mi", "como", "esta"},
    "de": {"der", "die", "das", "und", "ist", "ein", "eine", "ich", "nicht", "sie", "mit", "hallo", "danke", "für", "auf", "zu", "wie", "mein", "bin"},
    "it": {"il", "lo", "gli", "e", "è", "un", "una", "che", "di", "per", "ciao", "grazie", "con", "non", "sono", "mi", "come", "questo", "della"},
    "pt": {"o", "os", "as", "e", "é", "um", "uma", "que", "de", "para", "olá", "obrigado", "com", "não", "estou", "meu", "como", "você", "uma"},
    "nl": {"de", "het", "een", "en", "is", "ik", "je", "niet", "van", "dat", "hallo", "dank", "met", "voor", "mijn", "ben", "hoe"},
    "tr": {"ve", "bir", "bu", "için", "ben", "sen", "değil", "merhaba", "teşekkürler", "ile", "çok", "nasıl", "benim", "adım"},
}


def _bucket(char: str) -> Optional[str]:
    cp = ord(char)
    for start, end, name in _SCRIPT_RANGES:
        if start <= cp <= end:
            return name
    if char.isalpha() and cp < 0x250:
        return "latin"
    return None


def _tokens(text: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE)


def _detect_latin(text: str) -> Optional[str]:
    tokens = _tokens(text)
    if not tokens:
        return None
    scores = {code: sum(1 for t in tokens if t in words) for code, words in _STOPWORDS.items()}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_code, best = ranked[0]
    second = ranked[1][1]
    needed = 1 if len(tokens) <= 3 else 2
    if best >= needed and best > second:
        return best_code
    return None


def detect_language(text: str) -> Optional[str]:
    """Return a language code (e.g. ``"hi"``) or ``None`` when unsure."""
    if not text or not text.strip():
        return None
    counts = Counter(b for b in (_bucket(c) for c in text) if b)
    if not counts:
        return None
    dominant, hits = counts.most_common(1)[0]
    if hits / sum(counts.values()) < 0.4:
        return None

    if dominant == "latin":
        return _detect_latin(text)
    if dominant == "devanagari":
        words = set(_tokens(text)) | set(text.split())
        return "mr" if len(words & _MARATHI_MARKERS) > len(words & _HINDI_MARKERS) else "hi"
    if dominant == "arabic":
        return "ur" if any(c in _URDU_LETTERS for c in text) else "ar"
    if dominant in ("han", "kana"):
        return "ja" if counts.get("kana") else "zh-CN"
    return {
        "bengali": "bn", "tamil": "ta", "telugu": "te", "cyrillic": "ru", "hangul": "ko",
    }.get(dominant)
