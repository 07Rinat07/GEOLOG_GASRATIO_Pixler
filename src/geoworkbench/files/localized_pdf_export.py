from __future__ import annotations

from pathlib import Path
import zipfile

import fitz

from geoworkbench.files.pdf_tools import PdfTools, PdfToolsError


_EXPORT_TEXT: dict[str, dict[str, str]] = {
    "ru": {
        "page": "Страница {number}",
        "empty": "В PDF не найден распознаваемый текст.",
        "invalid": "Выберите существующий PDF",
        "protected": "PDF защищён паролем",
        "read_error": "Текст PDF не прочитан: {error}",
        "save_error": "DOCX не сохранён: {error}",
    },
    "kk": {
        "page": "{number}-бет",
        "empty": "PDF файлында танылатын мәтін табылмады.",
        "invalid": "Бар PDF файлын таңдаңыз",
        "protected": "PDF құпиясөзбен қорғалған",
        "read_error": "PDF мәтінін оқу мүмкін болмады: {error}",
        "save_error": "DOCX сақталмады: {error}",
    },
    "en": {
        "page": "Page {number}",
        "empty": "No recognizable text was found in the PDF.",
        "invalid": "Select an existing PDF",
        "protected": "The PDF is password protected",
        "read_error": "PDF text could not be read: {error}",
        "save_error": "DOCX was not saved: {error}",
    },
}


def export_catalogs_have_same_keys() -> bool:
    key_sets = [set(catalog) for catalog in _EXPORT_TEXT.values()]
    return all(keys == key_sets[0] for keys in key_sets[1:])


def export_text_docx_localized(source: Path, target: Path, *, language: str) -> Path:
    """Export selectable PDF text with localized generated headings and messages."""
    catalog = _EXPORT_TEXT.get(language, _EXPORT_TEXT["ru"])
    input_path = Path(source).resolve()
    destination = Path(target).resolve().with_suffix(".docx")
    if not input_path.is_file() or input_path.suffix.casefold() != ".pdf":
        raise PdfToolsError(catalog["invalid"])
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        with fitz.open(input_path) as document:
            if document.needs_pass:
                raise PdfToolsError(catalog["protected"])
            pages = [page.get_text("text").strip() for page in document]
    except (fitz.FileDataError, OSError, RuntimeError, ValueError) as exc:
        if isinstance(exc, PdfToolsError):
            raise
        raise PdfToolsError(catalog["read_error"].format(error=exc)) from exc

    paragraphs: list[str] = []
    for page_number, page_text in enumerate(pages, start=1):
        paragraphs.append(catalog["page"].format(number=page_number))
        paragraphs.extend(line for line in page_text.splitlines() if line.strip())
        if page_number < len(pages):
            paragraphs.append("")
    if not any(paragraph.strip() for paragraph in paragraphs):
        paragraphs = [catalog["empty"]]

    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", PdfTools._content_types_xml())
            archive.writestr("_rels/.rels", PdfTools._relationships_xml())
            archive.writestr("word/document.xml", PdfTools._document_xml(paragraphs))
        temporary.replace(destination)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise PdfToolsError(catalog["save_error"].format(error=exc)) from exc
    return destination
