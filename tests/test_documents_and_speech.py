"""Tests for document extraction and text-to-speech guard rails (no network)."""
import io

import docx
import pytest

from services.document_handler import (
    MAX_DOCUMENT_CHARS,
    MAX_FILE_BYTES,
    DocumentError,
    extract_text,
    format_size,
    validate_file,
)
from services.speech import SpeechError, is_supported, synthesize


def make_docx(paragraphs):
    document = docx.Document()
    for p in paragraphs:
        document.add_paragraph(p)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_pdf(text):
    """Build a minimal one-page PDF containing ``text`` (ASCII)."""
    stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objects) + 1, xref)
    return out


def test_txt_extraction_utf8_and_hindi():
    assert extract_text("a.txt", "नमस्ते दुनिया".encode("utf-8")) == "नमस्ते दुनिया"


def test_txt_falls_back_to_cp1252():
    assert extract_text("a.txt", "café".encode("cp1252")) == "café"


def test_docx_extraction():
    text = extract_text("a.docx", make_docx(["First paragraph.", "Second paragraph."]))
    assert "First paragraph." in text and "Second paragraph." in text


def test_pdf_extraction():
    assert "Hello PDF world" in extract_text("a.pdf", make_pdf("Hello PDF world"))


def test_unsupported_extension():
    with pytest.raises(DocumentError, match="Unsupported"):
        extract_text("malware.exe", b"data")
    with pytest.raises(DocumentError, match="Unsupported"):
        validate_file("noextension", 10)


def test_double_extension_is_judged_by_real_extension():
    with pytest.raises(DocumentError):
        validate_file("report.pdf.exe", 100)


def test_empty_and_oversized_files():
    with pytest.raises(DocumentError, match="empty"):
        validate_file("a.txt", 0)
    with pytest.raises(DocumentError, match="too large"):
        validate_file("a.txt", MAX_FILE_BYTES + 1)


def test_corrupted_files_give_friendly_errors():
    with pytest.raises(DocumentError, match="could not be read"):
        extract_text("a.pdf", b"this is not a pdf")
    with pytest.raises(DocumentError, match="could not be read"):
        extract_text("a.docx", b"this is not a docx")


def test_blank_document_rejected():
    with pytest.raises(DocumentError, match="No readable text"):
        extract_text("a.txt", b"   \n  ")


def test_document_character_limit():
    with pytest.raises(DocumentError, match="limit"):
        extract_text("a.txt", ("a" * (MAX_DOCUMENT_CHARS + 1)).encode())


def test_format_size():
    assert format_size(512) == "512 B"
    assert format_size(2048) == "2.0 KB"
    assert format_size(3 * 1024 * 1024) == "3.0 MB"


# --------------------------------------------------------------------- speech
def test_tts_rejects_empty_text():
    with pytest.raises(SpeechError, match="no text"):
        synthesize("  ", "en")


def test_tts_handles_unsupported_language_gracefully():
    assert not is_supported("xx")
    with pytest.raises(SpeechError, match="not available"):
        synthesize("hello", "xx")


def test_tts_rejects_too_long_text():
    with pytest.raises(SpeechError, match="too long"):
        synthesize("a" * 5000, "en")


def test_tts_calls_gtts_with_expected_arguments(monkeypatch):
    calls = {}

    class FakeGTTS:
        def __init__(self, text, lang):
            calls["args"] = (text, lang)

        def write_to_fp(self, fp):
            fp.write(b"MP3DATA")

    import sys, types
    module = types.ModuleType("gtts")
    module.gTTS = FakeGTTS
    monkeypatch.setitem(sys.modules, "gtts", module)
    assert synthesize(" नमस्ते ", "hi") == b"MP3DATA"
    assert calls["args"] == ("नमस्ते", "hi")


def test_tts_network_failure_becomes_speech_error(monkeypatch):
    class Boom:
        def __init__(self, *a, **k):
            pass

        def write_to_fp(self, fp):
            raise RuntimeError("network down")

    import sys, types
    module = types.ModuleType("gtts")
    module.gTTS = Boom
    monkeypatch.setitem(sys.modules, "gtts", module)
    with pytest.raises(SpeechError, match="Could not generate audio"):
        synthesize("hello", "en")
