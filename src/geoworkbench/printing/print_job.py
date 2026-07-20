from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from PySide6.QtGui import QImageWriter

from geoworkbench.printing.page_settings import PrintPageSettings
from geoworkbench.printing.pagination import PrintPaginationSettings, PrintRangeMode


class PrintOutputFormat(StrEnum):
    PRINTER = "printer"
    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"
    TIFF = "tiff"
    BMP = "bmp"
    WEBP = "webp"
    SVG = "svg"

    @property
    def is_file(self) -> bool:
        return self is not PrintOutputFormat.PRINTER

    @property
    def is_raster(self) -> bool:
        return self in {
            PrintOutputFormat.PNG,
            PrintOutputFormat.JPEG,
            PrintOutputFormat.TIFF,
            PrintOutputFormat.BMP,
            PrintOutputFormat.WEBP,
        }

    @property
    def suffix(self) -> str:
        return {
            PrintOutputFormat.PRINTER: "",
            PrintOutputFormat.PDF: ".pdf",
            PrintOutputFormat.PNG: ".png",
            PrintOutputFormat.JPEG: ".jpg",
            PrintOutputFormat.TIFF: ".tiff",
            PrintOutputFormat.BMP: ".bmp",
            PrintOutputFormat.WEBP: ".webp",
            PrintOutputFormat.SVG: ".svg",
        }[self]

    @property
    def qt_image_format(self) -> bytes:
        return {
            PrintOutputFormat.PNG: b"PNG",
            PrintOutputFormat.JPEG: b"JPEG",
            PrintOutputFormat.TIFF: b"TIFF",
            PrintOutputFormat.BMP: b"BMP",
            PrintOutputFormat.WEBP: b"WEBP",
        }.get(self, b"")

    @property
    def file_filter(self) -> str:
        return {
            PrintOutputFormat.PDF: "PDF (*.pdf)",
            PrintOutputFormat.PNG: "PNG (*.png)",
            PrintOutputFormat.JPEG: "JPEG (*.jpg *.jpeg)",
            PrintOutputFormat.TIFF: "TIFF (*.tif *.tiff)",
            PrintOutputFormat.BMP: "Bitmap (*.bmp)",
            PrintOutputFormat.WEBP: "WebP (*.webp)",
            PrintOutputFormat.SVG: "SVG (*.svg)",
            PrintOutputFormat.PRINTER: "",
        }[self]

    @property
    def accepted_suffixes(self) -> tuple[str, ...]:
        return {
            PrintOutputFormat.PRINTER: (),
            PrintOutputFormat.PDF: (".pdf",),
            PrintOutputFormat.PNG: (".png",),
            PrintOutputFormat.JPEG: (".jpg", ".jpeg", ".jfif"),
            PrintOutputFormat.TIFF: (".tif", ".tiff"),
            PrintOutputFormat.BMP: (".bmp",),
            PrintOutputFormat.WEBP: (".webp",),
            PrintOutputFormat.SVG: (".svg",),
        }[self]


@dataclass(frozen=True, slots=True)
class PrintJobSettings:
    output_format: PrintOutputFormat = PrintOutputFormat.PDF
    page: PrintPageSettings = field(default_factory=PrintPageSettings)
    dpi: int = 300
    image_quality: int = 92
    target: Path | None = None
    pagination: PrintPaginationSettings = field(default_factory=PrintPaginationSettings)
    strict_unicode: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.dpi, bool) or not isinstance(self.dpi, int) or not 72 <= self.dpi <= 600:
            raise ValueError("Разрешение должно быть от 72 до 600 DPI")
        if (
            isinstance(self.image_quality, bool)
            or not isinstance(self.image_quality, int)
            or not 1 <= self.image_quality <= 100
        ):
            raise ValueError("Качество изображения должно быть от 1 до 100")
        if not isinstance(self.strict_unicode, bool):
            raise ValueError("Unicode-проверка должна быть логическим значением")
        if self.output_format.is_file and self.target is None:
            raise ValueError("Для файлового экспорта необходимо выбрать путь")
        if not self.output_format.is_file and self.target is not None:
            raise ValueError("Для физического принтера путь к файлу не используется")

    def normalized_target(self) -> Path | None:
        if self.target is None:
            return None
        if self.target.suffix.casefold() in self.output_format.accepted_suffixes:
            return self.target
        return self.target.with_suffix(self.output_format.suffix)


@dataclass(frozen=True, slots=True)
class PrintExportPreferences:
    output_format: PrintOutputFormat = PrintOutputFormat.PDF
    dpi: int = 300
    image_quality: int = 92
    range_mode: PrintRangeMode = PrintRangeMode.CURRENT
    units_per_page: float = 50.0
    overlap: float = 0.0
    custom_start: float | None = None
    custom_end: float | None = None
    show_page_numbers: bool = True
    show_page_range: bool = True

    def __post_init__(self) -> None:
        if self.output_format is PrintOutputFormat.PRINTER:
            # The physical printer can still be selected in the dialog, but a
            # file format is a safer persistent default across computers.
            object.__setattr__(self, "output_format", PrintOutputFormat.PDF)
        if isinstance(self.dpi, bool) or not isinstance(self.dpi, int) or not 72 <= self.dpi <= 600:
            raise ValueError("Разрешение должно быть от 72 до 600 DPI")
        if (
            isinstance(self.image_quality, bool)
            or not isinstance(self.image_quality, int)
            or not 1 <= self.image_quality <= 100
        ):
            raise ValueError("Качество изображения должно быть от 1 до 100")
        PrintPaginationSettings(
            range_mode=self.range_mode,
            units_per_page=self.units_per_page,
            overlap=self.overlap,
            custom_start=self.custom_start,
            custom_end=self.custom_end,
            show_page_numbers=self.show_page_numbers,
            show_page_range=self.show_page_range,
        )


def available_output_formats() -> tuple[PrintOutputFormat, ...]:
    supported = {
        bytes(item).decode("ascii", errors="ignore").casefold()
        for item in QImageWriter.supportedImageFormats()
    }
    result = [PrintOutputFormat.PRINTER, PrintOutputFormat.PDF, PrintOutputFormat.PNG]
    for item, aliases in (
        (PrintOutputFormat.JPEG, {"jpeg", "jpg", "jfif"}),
        (PrintOutputFormat.TIFF, {"tif", "tiff"}),
        (PrintOutputFormat.BMP, {"bmp"}),
        (PrintOutputFormat.WEBP, {"webp"}),
    ):
        if supported.intersection(aliases):
            result.append(item)
    result.append(PrintOutputFormat.SVG)
    return tuple(result)
