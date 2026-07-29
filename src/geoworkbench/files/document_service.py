from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from pathlib import Path
from typing import Any

import fitz
from PIL import Image, ImageEnhance, ImageOps


class DocumentError(RuntimeError):
    pass


class DocumentKind(StrEnum):
    PDF = "pdf"
    IMAGE = "image"


@dataclass(frozen=True, slots=True)
class RenderedPage:
    payload: bytes
    width: int
    height: int
    scale: float
    page_index: int
    page_count: int


@dataclass(slots=True)
class _Snapshot:
    kind: DocumentKind
    payload: bytes
    page_index: int


_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


class DocumentService:
    """Stateful PDF/image editor used by the Files workspace."""

    def __init__(self) -> None:
        self.path: Path | None = None
        self.kind: DocumentKind | None = None
        self._pdf: fitz.Document | None = None
        self._image: Image.Image | None = None
        self._image_format = "PNG"
        self.page_index = 0
        self.dirty = False
        self._undo: list[_Snapshot] = []
        self._redo: list[_Snapshot] = []

    @property
    def is_open(self) -> bool:
        return self.kind is not None

    @property
    def page_count(self) -> int:
        if self.kind is DocumentKind.PDF and self._pdf is not None:
            return self._pdf.page_count
        return 1 if self.kind is DocumentKind.IMAGE and self._image is not None else 0

    @property
    def image_size(self) -> tuple[int, int] | None:
        return None if self._image is None else self._image.size

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def open(self, path: Path) -> DocumentKind:
        source = Path(path).resolve()
        if not source.is_file():
            raise DocumentError(f"Файл не найден: {source}")
        self.close()
        try:
            if source.suffix.casefold() == ".pdf":
                self._pdf = fitz.open(source)
                if self._pdf.needs_pass:
                    self._pdf.close()
                    self._pdf = None
                    raise DocumentError("PDF защищён паролем")
                self.kind = DocumentKind.PDF
            elif source.suffix.casefold() in _IMAGE_EXTENSIONS:
                with Image.open(source) as image:
                    image.seek(0)
                    ImageOps.exif_transpose(image)
                    self._image = ImageOps.exif_transpose(image).convert("RGBA")
                    self._image_format = self._format_for_suffix(source.suffix)
                self.kind = DocumentKind.IMAGE
            else:
                raise DocumentError("Поддерживаются PDF, JPEG, PNG, TIFF и BMP")
        except (fitz.FileDataError, OSError, ValueError) as exc:
            self.close()
            if isinstance(exc, DocumentError):
                raise
            raise DocumentError(f"Не удалось открыть файл: {exc}") from exc
        self.path = source
        self.page_index = 0
        self.dirty = False
        self._undo.clear()
        self._redo.clear()
        return self.kind

    def close(self) -> None:
        if self._pdf is not None:
            self._pdf.close()
        self.path = None
        self.kind = None
        self._pdf = None
        self._image = None
        self.page_index = 0
        self.dirty = False
        self._undo.clear()
        self._redo.clear()

    def render(self, zoom: float = 1.5) -> RenderedPage:
        if not 0.1 <= zoom <= 8.0:
            raise DocumentError("Масштаб должен быть от 10% до 800%")
        if self.kind is DocumentKind.PDF and self._pdf is not None:
            page = self._pdf.load_page(self.page_index)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            return RenderedPage(
                pixmap.tobytes("png"),
                pixmap.width,
                pixmap.height,
                zoom,
                self.page_index,
                self._pdf.page_count,
            )
        if self.kind is DocumentKind.IMAGE and self._image is not None:
            width = max(1, round(self._image.width * zoom))
            height = max(1, round(self._image.height * zoom))
            rendered = self._image.resize((width, height), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            rendered.save(buffer, format="PNG")
            return RenderedPage(buffer.getvalue(), width, height, zoom, 0, 1)
        raise DocumentError("Документ не открыт")

    def set_page(self, page_index: int) -> None:
        if self.kind is not DocumentKind.PDF or self._pdf is None:
            self.page_index = 0
            return
        if not 0 <= page_index < self._pdf.page_count:
            raise DocumentError("Страница выходит за диапазон документа")
        self.page_index = page_index

    def save(self) -> Path:
        if self.path is None:
            raise DocumentError("Для нового документа используйте «Сохранить как»")
        return self.save_as(self.path)

    def save_as(self, target: Path) -> Path:
        destination = Path(target).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if self.kind is DocumentKind.PDF and self._pdf is not None:
            if destination.suffix.casefold() != ".pdf":
                destination = destination.with_suffix(".pdf")
            temporary = destination.with_name(f".{destination.name}.tmp")
            if temporary.exists():
                temporary.unlink()
            try:
                self._pdf.save(temporary, garbage=4, deflate=True, clean=True)
                temporary.replace(destination)
            except (OSError, RuntimeError, ValueError) as exc:
                temporary.unlink(missing_ok=True)
                raise DocumentError(f"PDF не сохранён: {exc}") from exc
            if self.path == destination:
                self._reload_pdf(destination)
        elif self.kind is DocumentKind.IMAGE and self._image is not None:
            suffix = destination.suffix.casefold()
            if suffix not in _IMAGE_EXTENSIONS:
                destination = destination.with_suffix(".png")
                suffix = ".png"
            image_format = self._format_for_suffix(suffix)
            image = self._image
            if image_format in {"JPEG", "BMP"} and image.mode == "RGBA":
                background = Image.new("RGB", image.size, "white")
                background.paste(image, mask=image.getchannel("A"))
                image = background
            try:
                image.save(destination, format=image_format, quality=95)
            except OSError as exc:
                raise DocumentError(f"Изображение не сохранено: {exc}") from exc
            self._image_format = image_format
        else:
            raise DocumentError("Документ не открыт")
        self.path = destination
        self.dirty = False
        return destination

    def undo(self) -> None:
        if not self._undo:
            return
        current = self._snapshot()
        snapshot = self._undo.pop()
        self._redo.append(current)
        self._restore(snapshot)

    def redo(self) -> None:
        if not self._redo:
            return
        current = self._snapshot()
        snapshot = self._redo.pop()
        self._undo.append(current)
        self._restore(snapshot)

    def add_pdf_text(
        self,
        rect: tuple[float, float, float, float],
        text: str,
        *,
        font_size: float = 11.0,
        color: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        page = self._pdf_page()
        if not text.strip():
            raise DocumentError("Введите текст")
        self._begin_edit()
        target = fitz.Rect(*rect)
        remaining = page.insert_textbox(
            target,
            text,
            fontsize=max(4.0, min(72.0, font_size)),
            color=color,
            fontname="helv",
        )
        if remaining < 0:
            self.undo()
            raise DocumentError("Текст не помещается в выбранную область")
        self.dirty = True

    def add_pdf_highlight(self, rect: tuple[float, float, float, float]) -> None:
        page = self._pdf_page()
        self._begin_edit()
        annotation = page.add_highlight_annot(fitz.Rect(*rect))
        annotation.update()
        self.dirty = True

    def add_pdf_note(self, point: tuple[float, float], text: str) -> None:
        page = self._pdf_page()
        if not text.strip():
            raise DocumentError("Введите текст примечания")
        self._begin_edit()
        annotation = page.add_text_annot(fitz.Point(*point), text)
        annotation.update()
        self.dirty = True

    def redact_pdf_area(self, rect: tuple[float, float, float, float]) -> None:
        page = self._pdf_page()
        self._begin_edit()
        page.add_redact_annot(fitz.Rect(*rect), fill=(1.0, 1.0, 1.0))
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
        self.dirty = True

    def delete_pdf_annotations(self, rect: tuple[float, float, float, float]) -> int:
        page = self._pdf_page()
        target = fitz.Rect(*rect)
        matches = [annotation for annotation in page.annots() or () if annotation.rect.intersects(target)]
        if not matches:
            return 0
        self._begin_edit()
        for annotation in matches:
            page.delete_annot(annotation)
        self.dirty = True
        return len(matches)

    def resize_image(self, width: int, height: int) -> None:
        image = self._require_image()
        if not 1 <= width <= 100_000 or not 1 <= height <= 100_000:
            raise DocumentError("Размер изображения должен быть от 1 до 100000 пикселей")
        if width * height > 250_000_000:
            raise DocumentError("Изображение слишком большое")
        self._begin_edit()
        self._image = image.resize((width, height), Image.Resampling.LANCZOS)
        self.dirty = True

    def crop_image(self, rect: tuple[int, int, int, int]) -> None:
        image = self._require_image()
        left, top, right, bottom = rect
        left = max(0, min(image.width, left))
        right = max(0, min(image.width, right))
        top = max(0, min(image.height, top))
        bottom = max(0, min(image.height, bottom))
        if right - left < 1 or bottom - top < 1:
            raise DocumentError("Выделите область обрезки")
        self._begin_edit()
        self._image = image.crop((left, top, right, bottom))
        self.dirty = True

    def correct_image(
        self,
        *,
        brightness: float = 1.0,
        contrast: float = 1.0,
        color: float = 1.0,
        sharpness: float = 1.0,
        grayscale: bool = False,
        autocontrast: bool = False,
    ) -> None:
        image = self._require_image()
        values = (brightness, contrast, color, sharpness)
        if any(not 0.0 <= value <= 4.0 for value in values):
            raise DocumentError("Коэффициенты коррекции должны быть от 0 до 4")
        self._begin_edit()
        result = image
        if autocontrast:
            alpha = result.getchannel("A") if result.mode == "RGBA" else None
            rgb = ImageOps.autocontrast(result.convert("RGB"))
            result = rgb.convert("RGBA")
            if alpha is not None:
                result.putalpha(alpha)
        if grayscale:
            alpha = result.getchannel("A") if result.mode == "RGBA" else None
            result = ImageOps.grayscale(result).convert("RGBA")
            if alpha is not None:
                result.putalpha(alpha)
        result = ImageEnhance.Brightness(result).enhance(brightness)
        result = ImageEnhance.Contrast(result).enhance(contrast)
        result = ImageEnhance.Color(result).enhance(color)
        result = ImageEnhance.Sharpness(result).enhance(sharpness)
        self._image = result
        self.dirty = True

    def _begin_edit(self) -> None:
        self._undo.append(self._snapshot())
        if len(self._undo) > 20:
            del self._undo[0]
        self._redo.clear()

    def _snapshot(self) -> _Snapshot:
        if self.kind is DocumentKind.PDF and self._pdf is not None:
            return _Snapshot(
                DocumentKind.PDF,
                self._pdf.tobytes(garbage=4, deflate=True),
                self.page_index,
            )
        if self.kind is DocumentKind.IMAGE and self._image is not None:
            buffer = BytesIO()
            self._image.save(buffer, format="PNG")
            return _Snapshot(DocumentKind.IMAGE, buffer.getvalue(), 0)
        raise DocumentError("Документ не открыт")

    def _restore(self, snapshot: _Snapshot) -> None:
        if self._pdf is not None:
            self._pdf.close()
            self._pdf = None
        if snapshot.kind is DocumentKind.PDF:
            self._pdf = fitz.open(stream=snapshot.payload, filetype="pdf")
            self._image = None
            self.page_index = min(snapshot.page_index, max(0, self._pdf.page_count - 1))
        else:
            with Image.open(BytesIO(snapshot.payload)) as image:
                self._image = image.convert("RGBA")
            self._pdf = None
            self.page_index = 0
        self.kind = snapshot.kind
        self.dirty = True

    def _pdf_page(self) -> fitz.Page:
        if self.kind is not DocumentKind.PDF or self._pdf is None:
            raise DocumentError("Операция доступна только для PDF")
        return self._pdf.load_page(self.page_index)

    def _require_image(self) -> Image.Image:
        if self.kind is not DocumentKind.IMAGE or self._image is None:
            raise DocumentError("Операция доступна только для изображения")
        return self._image

    def _reload_pdf(self, path: Path) -> None:
        page_index = self.page_index
        if self._pdf is not None:
            self._pdf.close()
        self._pdf = fitz.open(path)
        self.page_index = min(page_index, max(0, self._pdf.page_count - 1))

    @staticmethod
    def _format_for_suffix(suffix: str) -> str:
        return {
            ".jpg": "JPEG",
            ".jpeg": "JPEG",
            ".png": "PNG",
            ".tif": "TIFF",
            ".tiff": "TIFF",
            ".bmp": "BMP",
        }.get(suffix.casefold(), "PNG")
