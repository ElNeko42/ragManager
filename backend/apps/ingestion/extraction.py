"""Turning a stored file into the plain text that will be indexed."""

import io

from apps.common import media_types
from apps.ingestion import imaging

MIN_CHARS_PER_PAGE = 80
TEXT_MEDIA_TYPES = {"application/json", "application/xml"}


class ExtractionError(Exception):
    """Raised when a file cannot be turned into text."""


def extract_text(data, media_type):
    """Extract the indexable text of a file.

    Takes the raw bytes and the media type, and picks the cheapest route that
    works: a text layer is read directly, and only a file without one goes
    through recognition, so nothing is spent on files that can be read for
    free. Returns the text. Raises ExtractionError for a type this build
    cannot read.
    """
    if media_type == media_types.PDF:
        return extract_pdf(data)
    if media_type.startswith("image/"):
        return imaging.describe(data, media_type)
    if media_type == media_types.WORD:
        return extract_word(data)
    if media_type.startswith("text/") or media_type in TEXT_MEDIA_TYPES:
        return data.decode("utf-8", errors="replace")
    raise ExtractionError(f"No extractor is available for '{media_type}'")


def extract_pdf(data):
    """Read a PDF, falling back to recognition when it is scanned.

    Takes the raw bytes. A scanned page carries an image and no characters, so
    when the text layer yields almost nothing the whole file goes through
    recognition instead. Returns the text.
    """
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    if len(text) >= MIN_CHARS_PER_PAGE * max(len(pages), 1):
        return text
    return imaging.describe(data, media_types.PDF)


def extract_word(data):
    """Read the paragraphs and tables of a Word document.

    Takes the raw bytes and returns the text. Table cells are included because
    a contract's figures often live only there.
    """
    from docx import Document as WordDocument

    document = WordDocument(io.BytesIO(data))
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" ".join(cell.text for cell in row.cells))
    return "\n".join(part for part in parts if part.strip())
