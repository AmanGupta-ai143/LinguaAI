"""Document validation and text extraction (TXT, PDF, DOCX)."""
from __future__ import annotations

import io
from pathlib import PurePath

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}
MAX_FILE_BYTES = 5 * 1024 * 1024     # 5 MB
MAX_DOCUMENT_CHARS = 20000           # keeps one document within a sensible API budget
MAX_PDF_PAGES = 100


class DocumentError(Exception):
    """Raised with a user-friendly message when a file cannot be processed."""


def format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB"):
        if size < 1024 or unit == "MB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} MB"


def validate_file(filename: str, size: int) -> str:
    """Check extension and size. Returns the lower-case extension."""
    ext = PurePath(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise DocumentError(
            f"Unsupported file type '{ext or 'unknown'}'. Please upload a TXT, PDF or DOCX file."
        )
    if size <= 0:
        raise DocumentError("The file is empty.")
    if size > MAX_FILE_BYTES:
        raise DocumentError(
            f"The file is too large ({format_size(size)}). The limit is {format_size(MAX_FILE_BYTES)}."
        )
    return ext


def _extract_txt(data: bytes) -> str:
    # UTF-16 only when a BOM is present - otherwise it "successfully" decodes almost any bytes.
    encodings = ["utf-8-sig", "cp1252"]
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        encodings.insert(0, "utf-16")
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except UnicodeError:
            continue
    raise DocumentError("Could not read the text file - its encoding is not supported.")


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError as exc:
        raise DocumentError("PDF support needs the pypdf package. Run: pip install pypdf") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise DocumentError("This PDF is password-protected and cannot be read.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise DocumentError(f"The PDF has too many pages ({len(reader.pages)}). The limit is {MAX_PDF_PAGES}.")
        pages = [(page.extract_text() or "") for page in reader.pages]
    except DocumentError:
        raise
    except (PyPdfError, ValueError, OSError, KeyError) as exc:
        raise DocumentError("The PDF could not be read. It may be corrupted.") from exc
    return "\n\n".join(p.strip() for p in pages if p.strip())


def _extract_docx(data: bytes) -> str:
    try:
        import docx
    except ImportError as exc:
        raise DocumentError("DOCX support needs python-docx. Run: pip install python-docx") from exc
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:  # python-docx raises several error types for bad zips/XML
        raise DocumentError("The DOCX file could not be read. It may be corrupted.") from exc
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                paragraphs.append(" | ".join(cells))
    return "\n\n".join(paragraphs)


def extract_text(filename: str, data: bytes) -> str:
    """Validate the file and return its text. Raises ``DocumentError`` on problems."""
    ext = validate_file(filename, len(data))
    extractor = {".txt": _extract_txt, ".pdf": _extract_pdf, ".docx": _extract_docx}[ext]
    text = extractor(data).replace("\x00", "").strip()
    if not text:
        hint = " It may be a scanned document (image-only); OCR is not supported." if ext == ".pdf" else ""
        raise DocumentError(f"No readable text was found in the file.{hint}")
    if len(text) > MAX_DOCUMENT_CHARS:
        raise DocumentError(
            f"The document has {len(text):,} characters; the limit is {MAX_DOCUMENT_CHARS:,}. "
            "Please upload a shorter document or split it."
        )
    return text
