"""Tests for translation logic. The HTTP layer is mocked - no network is needed."""
import json
from unittest.mock import MagicMock

import pytest
import requests

from services.language_detector import detect_language
from services.translator import (
    AUTO_DETECT,
    LANGUAGES,
    APIError,
    APITimeoutError,
    MAX_CHUNK_BYTES,
    MyMemoryProvider,
    QuotaExceededError,
    TranslationService,
    ValidationError,
    split_into_chunks,
    swap_languages,
)


def fake_response(translated="ok", status=200, http=200, details="", detected=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = http
    payload = {"responseData": {"translatedText": translated}, "responseStatus": status,
               "responseDetails": details}
    if detected:
        payload["responseData"]["detectedLanguage"] = detected
    resp.json.return_value = payload
    if http >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"{http}")
    else:
        resp.raise_for_status.return_value = None
    return resp


def make_service(*responses_or_exceptions):
    session = MagicMock()
    session.get.side_effect = list(responses_or_exceptions)
    provider = MyMemoryProvider(session=session, email="", retries=1, retry_delay=0)
    return TranslationService(provider), session


# ---------------------------------------------------------------- core translations
@pytest.mark.parametrize(
    "text, src, tgt, pair, answer",
    [
        ("Hello, how are you?", "English", "Hindi", "en|hi", "नमस्ते, आप कैसे हैं?"),
        ("नमस्ते, आप कैसे हैं?", "Hindi", "English", "hi|en", "Hello, how are you?"),
        ("Good morning", "English", "French", "en|fr", "Bonjour"),
    ],
)
def test_translation_pairs(text, src, tgt, pair, answer):
    service, session = make_service(fake_response(answer))
    result = service.translate(text, src, tgt)
    assert result.translated_text == answer
    params = session.get.call_args.kwargs["params"]
    assert params["langpair"] == pair
    assert params["q"] == text
    assert session.get.call_args.kwargs["timeout"] == (5, 15)


def test_html_entities_are_decoded():
    service, _ = make_service(fake_response("It&#39;s fine"))
    assert service.translate("C'est bien", "French", "English").translated_text == "It's fine"


# ---------------------------------------------------------------- validation
@pytest.mark.parametrize("bad", ["", "   ", "\n\t", None])
def test_empty_input_is_rejected_without_api_call(bad):
    service, session = make_service()
    with pytest.raises(ValidationError):
        service.translate(bad, "English", "Hindi")
    session.get.assert_not_called()


def test_text_over_limit_is_rejected():
    service, session = make_service()
    with pytest.raises(ValidationError, match="too long"):
        service.translate("a" * 5001, "English", "Hindi")
    session.get.assert_not_called()


def test_same_source_and_target_rejected():
    service, _ = make_service()
    with pytest.raises(ValidationError, match="same"):
        service.translate("Hello", "English", "English")


def test_unknown_languages_rejected():
    service, _ = make_service()
    with pytest.raises(ValidationError):
        service.translate("Hello", "English", "Klingon")
    with pytest.raises(ValidationError):
        service.translate("Hello", "Klingon", "English")


def test_at_least_15_languages_supported():
    assert len(LANGUAGES) >= 15


# ---------------------------------------------------------------- swapping
def test_swap_languages():
    assert swap_languages("English", "Hindi") == ("Hindi", "English")


def test_swap_with_auto_uses_detected_language():
    assert swap_languages(AUTO_DETECT, "Hindi", detected="English") == ("Hindi", "English")


def test_swap_with_auto_and_no_detection_fails():
    with pytest.raises(ValueError):
        swap_languages(AUTO_DETECT, "Hindi")


# ---------------------------------------------------------------- auto detection
def test_auto_detect_uses_local_detector_when_confident():
    service, session = make_service(fake_response("Hello"))
    result = service.translate("नमस्ते मेरा नाम राहुल है", AUTO_DETECT, "English")
    assert result.detected_code == "hi"
    assert session.get.call_args.kwargs["params"]["langpair"] == "hi|en"


def test_auto_detect_falls_back_to_api_autodetect():
    service, session = make_service(fake_response("Hallo", detected="fr-FR"))
    result = service.translate("xyzzy plugh", AUTO_DETECT, "German")
    assert session.get.call_args.kwargs["params"]["langpair"] == "Autodetect|de"
    assert result.detected_code == "fr"


@pytest.mark.parametrize(
    "text, code",
    [
        ("Hello, how are you doing today?", "en"),
        ("Bonjour, je suis très content de vous voir", "fr"),
        ("Hola, ¿cómo estás? Estoy muy bien", "es"),
        ("Ich bin nicht sicher, was das ist", "de"),
        ("मेरा नाम राहुल है और मैं पटना में रहता हूँ", "hi"),
        ("माझे नाव राहुल आहे आणि मी पटण्यात राहतो", "mr"),
        ("こんにちは、元気ですか", "ja"),
        ("안녕하세요 반갑습니다", "ko"),
        ("Привет, как дела?", "ru"),
        ("你好，今天天气很好", "zh-CN"),
        ("مرحبا كيف حالك", "ar"),
        ("آپ کیسے ہیں؟ میں ٹھیک ہوں", "ur"),
        ("আমি ভালো আছি", "bn"),
    ],
)
def test_language_detection(text, code):
    assert detect_language(text) == code


def test_detection_returns_none_when_unsure():
    assert detect_language("") is None
    assert detect_language("12345 !!!") is None
    assert detect_language("xyzzy plugh") is None


# ---------------------------------------------------------------- long text / chunking
def test_chunks_respect_byte_limit_for_latin_text():
    text = " ".join(f"This is sentence number {i}, written to be reasonably long." for i in range(200))
    chunks = split_into_chunks(text)
    assert len(chunks) > 5
    assert all(len(c.encode("utf-8")) <= MAX_CHUNK_BYTES for c in chunks)
    assert " ".join(chunks).split() == text.split()  # nothing lost


def test_chunks_respect_byte_limit_for_hindi_text():
    text = "यह एक परीक्षण वाक्य है। " * 120
    chunks = split_into_chunks(text)
    assert all(len(c.encode("utf-8")) <= MAX_CHUNK_BYTES for c in chunks)


def test_single_huge_word_is_hard_split():
    chunks = split_into_chunks("x" * 2000)
    assert all(len(c.encode("utf-8")) <= MAX_CHUNK_BYTES for c in chunks)
    assert "".join(chunks) == "x" * 2000


def test_long_text_is_translated_in_multiple_requests_and_reported():
    text = " ".join(f"Sentence number {i} is here." for i in range(100))
    chunks = split_into_chunks(text)
    service, session = make_service(*[fake_response(f"T{i}") for i in range(len(chunks))])
    progress = []
    result = service.translate(text, "English", "French", progress_callback=lambda d, t: progress.append((d, t)))
    assert session.get.call_count == len(chunks) == result.chunks
    assert progress[-1] == (len(chunks), len(chunks))
    assert result.translated_text.startswith("T0 T1")


def test_paragraph_breaks_are_preserved():
    service, _ = make_service(fake_response("Un"), fake_response("Deux"))
    result = service.translate("One\n\nTwo", "English", "French")
    assert result.translated_text == "Un\n\nDeux"


# ---------------------------------------------------------------- API failures
def test_timeout_is_retried_then_reported():
    service, session = make_service(requests.Timeout(), requests.Timeout())
    with pytest.raises(APITimeoutError):
        service.translate("Hello", "English", "Hindi")
    assert session.get.call_count == 2


def test_timeout_then_success_recovers():
    service, _ = make_service(requests.Timeout(), fake_response("नमस्ते"))
    assert service.translate("Hello", "English", "Hindi").translated_text == "नमस्ते"


def test_connection_error_gives_friendly_message():
    service, _ = make_service(requests.ConnectionError(), requests.ConnectionError())
    with pytest.raises(APIError, match="internet"):
        service.translate("Hello", "English", "Hindi")


def test_http_500_is_reported():
    service, _ = make_service(fake_response("", http=500))
    with pytest.raises(APIError, match="500"):
        service.translate("Hello", "English", "Hindi")


def test_http_429_is_quota_error():
    service, _ = make_service(fake_response("", http=429))
    with pytest.raises(QuotaExceededError):
        service.translate("Hello", "English", "Hindi")


def test_quota_warning_text_is_not_returned_as_translation():
    warning = "MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS FOR TODAY."
    service, _ = make_service(fake_response(warning, status=200))
    with pytest.raises(QuotaExceededError):
        service.translate("Hello", "English", "Hindi")


def test_api_error_status_is_reported_with_details():
    service, _ = make_service(fake_response("", status="403", details="INVALID TARGET LANGUAGE"))
    with pytest.raises(APIError, match="INVALID TARGET LANGUAGE"):
        service.translate("Hello", "English", "Hindi")


def test_malformed_json_is_reported():
    resp = fake_response("x")
    resp.json.side_effect = json.JSONDecodeError("bad", "", 0)
    service, _ = make_service(resp)
    with pytest.raises(APIError, match="unreadable"):
        service.translate("Hello", "English", "Hindi")


def test_no_fake_result_on_failure():
    """On any failure the service raises - it never returns made-up text."""
    service, _ = make_service(fake_response("", status=500))
    with pytest.raises(APIError):
        service.translate("Hello", "English", "Hindi")
