"""Raw text extraction from PDF / DOCX uploads, plus URL fetching for JDs."""
from __future__ import annotations
import io
import re

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from docx import Document as DocxDocument

from ..config import settings


class ExtractionError(Exception):
    """User-actionable extraction failure."""


def extract_pdf_text(data: bytes) -> tuple[str, list[str]]:
    warnings: list[str] = []
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError(
            "This PDF could not be read. If it is password-protected, remove the "
            "password and upload again."
        ) from exc
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(
                "This PDF is password-protected. Remove the password and upload again."
            ) from exc
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            pages.append("")
    text = "\n\n".join(pages)
    if pages and len(text.strip()) < settings.TEXT_PER_PAGE_FLOOR * len(pages):
        warnings.append(
            "This PDF appears to contain little or no selectable text — it may be a "
            "scan or an image-based export. Please upload a text-based PDF or a DOCX "
            "for reliable parsing."
        )
    return text, warnings


def extract_docx_text(data: bytes) -> str:
    try:
        doc = DocxDocument(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError(
            "This DOCX could not be read. Try re-saving it from Word or LibreOffice."
        ) from exc
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:  # tolerate table-based CV layouts
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def extract_any(filename: str, data: bytes, mime: str = "") -> tuple[str, list[str]]:
    name = (filename or "").lower()
    if name.endswith(".pdf") or mime == "application/pdf":
        return extract_pdf_text(data)
    if name.endswith(".docx") or "wordprocessingml" in mime:
        return extract_docx_text(data), []
    if name.endswith(".doc") or mime == "application/msword":
        raise ExtractionError(
            "Legacy .doc files are not supported. Re-save the file as .docx or PDF."
        )
    raise ExtractionError("Unsupported file type. Upload a PDF or DOCX.")


_URL_RX = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)


def find_urls(text: str) -> list[str]:
    return _URL_RX.findall(text or "")


def fetch_url_text(url: str) -> str:
    """Fetch a JD URL and extract the main readable content."""
    if not url.lower().startswith(("http://", "https://")):
        raise ExtractionError("That does not look like a URL.")
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (compatible; CVTailorBot/1.0)"
        })
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code in (401, 403):
            raise ExtractionError(
                "The JD link requires a login or blocks bots. Copy the JD text and "
                "paste it instead."
            ) from exc
        raise ExtractionError(
            f"The JD link returned HTTP {code}. Open it in your browser and paste "
            "the text instead."
        ) from exc
    except httpx.HTTPError as exc:
        raise ExtractionError(
            f"Could not reach the JD link ({exc.__class__.__name__}). Paste the "
            "text instead."
        ) from exc
    if resp.status_code != 200:
        raise ExtractionError(
            f"The JD link returned HTTP {resp.status_code}. Open it in your browser "
            "and paste the text instead."
        )
    ctype = resp.headers.get("content-type", "")
    if "pdf" in ctype:
        text, warnings = extract_pdf_text(resp.content)
        return text
    soup = BeautifulSoup(resp.text, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.find("div", id="job-description") \
        or soup.find("div", class_=re.compile(r"job|description|posting", re.I)) or soup.body or soup
    text = main.get_text("\n")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 200:
        raise ExtractionError(
            "The page did not contain readable job-description content (it may be a "
            "login wall or a JS-rendered page). Paste the JD text instead."
        )
    return text
