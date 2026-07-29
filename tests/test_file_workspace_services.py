from __future__ import annotations

from pathlib import Path
import zipfile

import fitz
import pytest
from PIL import Image

from geoworkbench.files.archive_service import ArchiveError, ArchiveFormat, ArchiveService
from geoworkbench.files.datum import calculate_datum_elevations
from geoworkbench.files.document_service import DocumentKind, DocumentService
from geoworkbench.files.engineering import (
    EngineeringCalculator,
    EngineeringExpressionError,
    UnitConverter,
)
from geoworkbench.files.logo_service import LogoDesign, LogoService
from geoworkbench.files.pdf_tools import PdfTools


def _write_pdf(path: Path, text: str, pages: int = 1) -> None:
    document = fitz.open()
    try:
        for page_number in range(pages):
            page = document.new_page()
            page.insert_text((72, 72), f"{text} {page_number + 1}")
        document.save(path)
    finally:
        document.close()


def test_engineering_calculator_supports_fractional_inches() -> None:
    calculator = EngineeringCalculator()
    assert calculator.evaluate("2 1/2 + 1/4") == pytest.approx(2.75)
    assert calculator.evaluate("sqrt(144) + sin(pi / 2)") == pytest.approx(13.0)


def test_engineering_calculator_rejects_python_execution() -> None:
    calculator = EngineeringCalculator()
    with pytest.raises(EngineeringExpressionError):
        calculator.evaluate("__import__('os').system('echo unsafe')")


def test_unit_converter_handles_mixed_fraction() -> None:
    converter = UnitConverter()
    millimetres = converter.convert("1 1/2", "length", "in", "mm")
    assert millimetres == pytest.approx(38.1)


def test_datum_chain_resolves_common_rig_references() -> None:
    elevations = calculate_datum_elevations(
        datum_elevation_m=100.0,
        gl_offset_m=2.0,
        wellhead_above_gl_m=1.2,
        df_above_gl_m=6.0,
        rt_above_df_m=0.5,
        kb_above_rt_m=0.3,
    )
    assert elevations.ground_level_m == pytest.approx(102.0)
    assert elevations.wellhead_m == pytest.approx(103.2)
    assert elevations.drill_floor_m == pytest.approx(108.0)
    assert elevations.rotary_table_m == pytest.approx(108.5)
    assert elevations.kelly_bushing_m == pytest.approx(108.8)


def test_archive_service_creates_and_extracts_zip(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "note.txt").write_text("well file", encoding="utf-8")
    service = ArchiveService()

    archive = service.create(tmp_path / "bundle", [source], ArchiveFormat.ZIP)
    assert archive.name == "bundle.zip"
    entries = service.list_entries(archive)
    assert any(entry.name.endswith("note.txt") for entry in entries)

    destination = tmp_path / "extracted"
    extracted = service.extract(archive, destination)
    assert len(extracted) == 1
    assert (destination / "source" / "note.txt").read_text(encoding="utf-8") == "well file"


def test_archive_service_blocks_zip_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../outside.txt", "unsafe")
    service = ArchiveService()

    with pytest.raises(ArchiveError, match="Опасный путь"):
        service.extract(archive, tmp_path / "target")
    assert not (tmp_path / "outside.txt").exists()


def test_document_service_edits_and_saves_image(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (40, 20), "white").save(source)
    service = DocumentService()

    assert service.open(source) is DocumentKind.IMAGE
    service.resize_image(80, 40)
    service.correct_image(brightness=0.8, contrast=1.2)
    target = service.save_as(tmp_path / "edited.png")

    with Image.open(target) as image:
        assert image.size == (80, 40)


def test_pdf_tools_merge_split_and_export_docx(tmp_path: Path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    _write_pdf(first, "FIRST")
    _write_pdf(second, "SECOND", pages=2)

    merged = PdfTools.merge([first, second], tmp_path / "merged.pdf")
    with fitz.open(merged) as document:
        assert document.page_count == 3

    pages = PdfTools.split(merged, tmp_path / "pages")
    assert len(pages) == 3
    assert all(path.is_file() for path in pages)

    docx = PdfTools.export_text_docx(merged, tmp_path / "merged.docx")
    with zipfile.ZipFile(docx) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    assert "FIRST" in xml
    assert "SECOND" in xml


def test_logo_service_creates_transparent_png(tmp_path: Path) -> None:
    service = LogoService()
    design = LogoDesign(
        text="BPServices",
        width=600,
        height=180,
        font_size=72,
        transparent_background=True,
        border_width=2,
    )
    target = service.save(design, tmp_path / "logo.png")

    with Image.open(target) as image:
        assert image.size == (600, 180)
        assert image.mode == "RGBA"
