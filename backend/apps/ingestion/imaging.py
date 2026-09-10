"""Turning files that carry no text layer into text."""

import base64
import io

import httpx
from django.conf import settings

DESCRIPTION_PROMPT = (
    "Transcribe every piece of text in this file, in reading order, and then "
    "describe any diagram, table, chart or photograph it contains, including "
    "the figures they show. The result is stored as the searchable text of "
    "this file, so write plain prose with no preamble and no commentary "
    "about the task."
)
API_TIMEOUT_SECONDS = 300
MAX_DESCRIPTION_TOKENS = 8000
SCAN_DPI = 200


class ImagingError(Exception):
    """Raised when a file without a text layer cannot be read."""


def vision_is_configured():
    """Report whether a vision endpoint has been configured.

    Vision is the optional upgrade over local OCR: better on handwriting,
    diagrams and complex layouts, but it costs money and needs an account.
    """
    return bool(settings.VISION_BASE_URL and settings.VISION_MODEL)


def describe(data, media_type):
    """Read a file that has no text layer.

    Takes the raw bytes and their media type. Uses the configured vision
    endpoint when there is one and local OCR otherwise, so the stack indexes
    scans out of the box without an account anywhere. Returns the text.
    """
    if vision_is_configured():
        return describe_through_api(data, media_type)
    return read_with_ocr(data, media_type)


def read_with_ocr(data, media_type):
    """Read a scan with the OCR engine bundled in the image.

    Takes the raw bytes and their media type, rasterising a PDF page by page
    first. Returns the recognised text. Raises ImagingError when the engine is
    missing or the file cannot be rendered.
    """
    import pytesseract
    from PIL import Image

    try:
        if media_type == "application/pdf":
            from pdf2image import convert_from_bytes

            pages = convert_from_bytes(data, dpi=SCAN_DPI)
        else:
            pages = [Image.open(io.BytesIO(data))]
        recognised = [
            pytesseract.image_to_string(page, lang=settings.OCR_LANGUAGES) for page in pages
        ]
    except Exception as error:
        raise ImagingError(
            f"Optical recognition failed: {type(error).__name__}: {error}"
        ) from error
    return "\n".join(part.strip() for part in recognised if part.strip())


def describe_through_api(data, media_type):
    """Describe a file through an OpenAI compatible chat endpoint.

    Takes the raw bytes and their media type. A PDF is rasterised first,
    because the image content block is the part of that shape every provider
    implements the same way. Returns the description. Raises ImagingError when
    the service answers with an error or an unexpected body.
    """
    images = rasterise(data, media_type)
    content = [{"type": "text", "text": DESCRIPTION_PROMPT}]
    for image_bytes, image_type in images:
        encoded = base64.standard_b64encode(image_bytes).decode("ascii")
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:{image_type};base64,{encoded}"}}
        )
    headers = {"Content-Type": "application/json"}
    if settings.VISION_API_KEY:
        headers["Authorization"] = f"Bearer {settings.VISION_API_KEY}"
    try:
        response = httpx.post(
            f"{settings.VISION_BASE_URL.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": settings.VISION_MODEL,
                "max_tokens": MAX_DESCRIPTION_TOKENS,
                "messages": [{"role": "user", "content": content}],
            },
            timeout=API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except httpx.HTTPError as error:
        raise ImagingError(f"The vision endpoint failed: {error}") from error
    except (KeyError, IndexError, ValueError) as error:
        raise ImagingError(
            f"The vision endpoint returned an unexpected body: {error}"
        ) from error


def rasterise(data, media_type):
    """Render a file as a list of images ready to send to a vision endpoint.

    Takes the raw bytes and their media type. Returns a list of (bytes, media
    type) pairs, one per page for a PDF and a single entry for an image.
    """
    if media_type != "application/pdf":
        return [(data, media_type)]
    from pdf2image import convert_from_bytes

    rendered = []
    for page in convert_from_bytes(data, dpi=SCAN_DPI):
        buffer = io.BytesIO()
        page.save(buffer, format="PNG")
        rendered.append((buffer.getvalue(), "image/png"))
    return rendered
