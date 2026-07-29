from __future__ import annotations

from html import escape
from pathlib import Path
import tempfile
import zipfile

import fitz


class PdfToolsError(RuntimeError):
    """Raised when a PDF utility operation cannot be completed safely."""


class PdfTools:
    """Standalone merge, split and PDF-to-DOCX operations for the Files tab."""

    @staticmethod
    def merge(sources: list[Path] | tuple[Path, ...], target: Path) -> Path:
        paths = tuple(Path(source).resolve() for source in sources)
        if len(paths) < 2:
            raise PdfToolsError("Для объединения выберите не менее двух PDF")
        destination = Path(target).resolve().with_suffix(".pdf")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination in paths:
            raise PdfToolsError("Результат не должен совпадать с исходным PDF")

        output = fitz.open()
        try:
            for source in paths:
                if not source.is_file() or source.suffix.casefold() != ".pdf":
                    raise PdfToolsError(f"Некорректный PDF: {source}")
                with fitz.open(source) as document:
                    if document.needs_pass:
                        raise PdfToolsError(f"PDF защищён паролем: {source.name}")
                    output.insert_pdf(document)
            if output.page_count == 0:
                raise PdfToolsError("В исходных документах нет страниц")
            PdfTools._save_pdf_atomic(output, destination)
        except (fitz.FileDataError, OSError, RuntimeError, ValueError) as exc:
            if isinstance(exc, PdfToolsError):
                raise
            raise PdfToolsError(f"PDF не объединён: {exc}") from exc
        finally:
            output.close()
        return destination

    @staticmethod
    def split(source: Path, destination: Path) -> tuple[Path, ...]:
        input_path = Path(source).resolve()
        output_dir = Path(destination).resolve()
        if not input_path.is_file() or input_path.suffix.casefold() != ".pdf":
            raise PdfToolsError("Выберите существующий PDF")
        output_dir.mkdir(parents=True, exist_ok=True)
        results: list[Path] = []
        try:
            with fitz.open(input_path) as document:
                if document.needs_pass:
                    raise PdfToolsError("PDF защищён паролем")
                width = max(3, len(str(document.page_count)))
                stem = input_path.stem
                for page_index in range(document.page_count):
                    output = fitz.open()
                    try:
                        output.insert_pdf(document, from_page=page_index, to_page=page_index)
                        target = output_dir / f"{stem}_page_{page_index + 1:0{width}d}.pdf"
                        target = PdfTools._unique_path(target)
                        PdfTools._save_pdf_atomic(output, target)
                        results.append(target)
                    finally:
                        output.close()
        except (fitz.FileDataError, OSError, RuntimeError, ValueError) as exc:
            if isinstance(exc, PdfToolsError):
                raise
            raise PdfToolsError(f"PDF не разделён: {exc}") from exc
        return tuple(results)

    @staticmethod
    def export_text_docx(source: Path, target: Path) -> Path:
        """Export selectable PDF text as editable paragraphs without layout claims."""

        input_path = Path(source).resolve()
        destination = Path(target).resolve().with_suffix(".docx")
        if not input_path.is_file() or input_path.suffix.casefold() != ".pdf":
            raise PdfToolsError("Выберите существующий PDF")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with fitz.open(input_path) as document:
                if document.needs_pass:
                    raise PdfToolsError("PDF защищён паролем")
                pages = [page.get_text("text").strip() for page in document]
        except (fitz.FileDataError, OSError, RuntimeError, ValueError) as exc:
            if isinstance(exc, PdfToolsError):
                raise
            raise PdfToolsError(f"Текст PDF не прочитан: {exc}") from exc

        paragraphs: list[str] = []
        for page_number, text in enumerate(pages, start=1):
            paragraphs.append(f"Страница {page_number}")
            paragraphs.extend(line for line in text.splitlines() if line.strip())
            if page_number < len(pages):
                paragraphs.append("")
        if not any(paragraph.strip() for paragraph in paragraphs):
            paragraphs = ["В PDF не найден распознаваемый текст."]

        document_xml = PdfTools._document_xml(paragraphs)
        temporary = destination.with_name(f".{destination.name}.tmp")
        temporary.unlink(missing_ok=True)
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("[Content_Types].xml", PdfTools._content_types_xml())
                archive.writestr("_rels/.rels", PdfTools._relationships_xml())
                archive.writestr("word/document.xml", document_xml)
            temporary.replace(destination)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise PdfToolsError(f"DOCX не сохранён: {exc}") from exc
        return destination

    @staticmethod
    def export_pages_docx(source: Path, target: Path, *, render_scale: float = 2.0) -> Path:
        """Place each rendered PDF page into Word while preserving visual appearance.

        The page remains an image inside DOCX, so tables, drawings, signatures and exact
        positioning are retained. Text is intentionally not advertised as editable.
        """

        input_path = Path(source).resolve()
        destination = Path(target).resolve().with_suffix(".docx")
        if not input_path.is_file() or input_path.suffix.casefold() != ".pdf":
            raise PdfToolsError("Выберите существующий PDF")
        if not 0.5 <= render_scale <= 4.0:
            raise PdfToolsError("Масштаб экспорта должен быть от 0,5 до 4")
        destination.parent.mkdir(parents=True, exist_ok=True)

        images: list[tuple[str, bytes, int, int]] = []
        try:
            with fitz.open(input_path) as document:
                if document.needs_pass:
                    raise PdfToolsError("PDF защищён паролем")
                if document.page_count == 0:
                    raise PdfToolsError("В PDF нет страниц")
                for page_index, page in enumerate(document):
                    pixmap = page.get_pixmap(
                        matrix=fitz.Matrix(render_scale, render_scale),
                        alpha=False,
                    )
                    filename = f"page_{page_index + 1:04d}.png"
                    images.append((filename, pixmap.tobytes("png"), pixmap.width, pixmap.height))
        except (fitz.FileDataError, OSError, RuntimeError, ValueError) as exc:
            if isinstance(exc, PdfToolsError):
                raise
            raise PdfToolsError(f"Страницы PDF не подготовлены: {exc}") from exc

        specs: list[tuple[str, int, int]] = []
        for index, (_name, _payload, width_px, height_px) in enumerate(images, start=1):
            width_emu, height_emu = PdfTools._fit_image_emu(width_px, height_px)
            specs.append((f"rId{index}", width_emu, height_emu))

        temporary = destination.with_name(f".{destination.name}.tmp")
        temporary.unlink(missing_ok=True)
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "[Content_Types].xml",
                    PdfTools._content_types_xml(include_png=True),
                )
                archive.writestr("_rels/.rels", PdfTools._relationships_xml())
                archive.writestr("word/document.xml", PdfTools._image_document_xml(specs))
                archive.writestr(
                    "word/_rels/document.xml.rels",
                    PdfTools._image_relationships_xml([item[0] for item in images]),
                )
                for filename, payload, _width, _height in images:
                    archive.writestr(f"word/media/{filename}", payload)
            temporary.replace(destination)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise PdfToolsError(f"DOCX со страницами не сохранён: {exc}") from exc
        return destination

    @staticmethod
    def _fit_image_emu(width_px: int, height_px: int) -> tuple[int, int]:
        emu_per_inch = 914_400
        max_width_in = 7.45
        max_height_in = 10.65
        aspect = width_px / max(1, height_px)
        width_in = max_width_in
        height_in = width_in / max(aspect, 1e-9)
        if height_in > max_height_in:
            height_in = max_height_in
            width_in = height_in * aspect
        return round(width_in * emu_per_inch), round(height_in * emu_per_inch)

    @staticmethod
    def _image_document_xml(specs: list[tuple[str, int, int]]) -> str:
        paragraphs: list[str] = []
        for index, (relationship_id, width_emu, height_emu) in enumerate(specs, start=1):
            paragraphs.append(
                '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
                f'<wp:inline distT="0" distB="0" distL="0" distR="0">'
                f'<wp:extent cx="{width_emu}" cy="{height_emu}"/>'
                f'<wp:docPr id="{index}" name="PDF page {index}"/>'
                '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                '<pic:pic><pic:nvPicPr>'
                f'<pic:cNvPr id="{index}" name="PDF page {index}"/><pic:cNvPicPr/>'
                '</pic:nvPicPr><pic:blipFill>'
                f'<a:blip r:embed="{relationship_id}"/><a:stretch><a:fillRect/></a:stretch>'
                '</pic:blipFill><pic:spPr>'
                f'<a:xfrm><a:off x="0" y="0"/><a:ext cx="{width_emu}" cy="{height_emu}"/></a:xfrm>'
                '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
                '</pic:spPr></pic:pic></a:graphicData></a:graphic>'
                '</wp:inline></w:drawing></w:r></w:p>'
            )
            if index < len(specs):
                paragraphs.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        paragraphs.append(
            '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="567" w:right="567" w:bottom="567" w:left="567"/>'
            '</w:sectPr>'
        )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document '
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<w:body>{"".join(paragraphs)}</w:body></w:document>'
        )

    @staticmethod
    def _image_relationships_xml(filenames: list[str]) -> str:
        items = []
        for index, filename in enumerate(filenames, start=1):
            items.append(
                f'<Relationship Id="rId{index}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                f'Target="media/{filename}"/>'
            )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{"".join(items)}</Relationships>'
        )

    @staticmethod
    def _save_pdf_atomic(document: fitz.Document, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.stem}-",
            suffix=".pdf",
            dir=destination.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
        try:
            document.save(temporary, garbage=4, deflate=True, clean=True)
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _unique_path(path: Path) -> Path:
        if not path.exists():
            return path
        counter = 2
        while True:
            candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def _document_xml(paragraphs: list[str]) -> str:
        body = []
        for paragraph in paragraphs:
            text = escape(paragraph)
            body.append(
                '<w:p><w:r><w:t xml:space="preserve">'
                f"{text}"
                "</w:t></w:r></w:p>"
            )
        body.append(
            '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/>'
            "</w:sectPr>"
        )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{''.join(body)}</w:body></w:document>"
        )

    @staticmethod
    def _content_types_xml(*, include_png: bool = False) -> str:
        png = (
            '<Default Extension="png" ContentType="image/png"/>'
            if include_png
            else ""
        )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f"{png}"
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        )

    @staticmethod
    def _relationships_xml() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            "</Relationships>"
        )
