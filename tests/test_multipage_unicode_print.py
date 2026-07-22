from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtGui import QFontDatabase
from PySide6.QtPdf import QPdfDocument

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.printing.document_export import export_document_pages, export_document_pdf
from geoworkbench.printing.document_renderer import PrintDocumentContext
from geoworkbench.printing.pagination import (
    PrintPaginationSettings,
    PrintRangeMode,
    build_page_slices,
)
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
from geoworkbench.printing.unicode_support import UnicodePrintError, preflight_texts
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


def test_full_range_is_split_into_stable_depth_pages() -> None:
    pages = build_page_slices(
        pagination=PrintPaginationSettings(
            range_mode=PrintRangeMode.FULL,
            units_per_page=50.0,
        ),
        current_range=(100.0, 150.0),
        full_range=(100.0, 300.0),
    )

    assert [(page.start, page.end) for page in pages] == [
        (100.0, 150.0),
        (150.0, 200.0),
        (200.0, 250.0),
        (250.0, 300.0),
    ]
    assert all(page.total == 4 for page in pages)


def test_unicode_preflight_accepts_three_languages_and_engineering_symbols(qapp) -> None:
    _require_system_fonts()
    report = preflight_texts(
        [
            "Глубина, скважина, газовый каротаж",
            "Тереңдік, ұңғыма, қазақша: Ә Ғ Қ Ң Ө Ұ Ү Һ І",
            "Depth ± 0.5 m; ΔP ≥ 10; µg/L; Ω; φ; ρ",
        ]
    )

    assert report.ok
    assert not report.missing_glyphs


def test_unicode_preflight_rejects_replacement_character(qapp) -> None:
    report = preflight_texts(["Повреждённый текст: \ufffd"])

    assert not report.ok
    assert "U+FFFD" in report.error_message()


def test_unicode_preflight_rejects_typical_cyrillic_mojibake(qapp) -> None:
    report = preflight_texts(["Ð“Ð»ÑƒÐ±Ð¸Ð½Ð° 100–150 Ð¼"])

    assert not report.ok
    assert "ошибочной перекодировки" in report.error_message()


def test_full_depth_pdf_contains_multiple_pages_and_restores_view(qapp, tmp_path) -> None:
    _require_system_fonts()
    view = _paged_tablet(qapp)
    original = view.visible_depth_range
    target = tmp_path / "толық_ұңғыма.pdf"
    job = PrintJobSettings(
        output_format=PrintOutputFormat.PDF,
        target=target,
        dpi=96,
        pagination=PrintPaginationSettings(
            range_mode=PrintRangeMode.FULL,
            units_per_page=50.0,
        ),
    )

    result = export_document_pdf(
        view,
        target,
        job,
        context=PrintDocumentContext("Скважина Ә-1 — Газовый каротаж", AppLanguage.RU),
    )

    document = QPdfDocument()
    assert document.load(str(target)) == QPdfDocument.Error.None_
    assert document.pageCount() == 4
    assert result.page_count == 4
    assert view.visible_depth_range == pytest.approx(original)
    view.close()


def test_full_depth_png_export_creates_numbered_pages(qapp, tmp_path) -> None:
    _require_system_fonts()
    view = _paged_tablet(qapp)
    target = tmp_path / "well.png"
    job = PrintJobSettings(
        output_format=PrintOutputFormat.PNG,
        target=target,
        dpi=72,
        pagination=PrintPaginationSettings(
            range_mode=PrintRangeMode.FULL,
            units_per_page=100.0,
        ),
    )

    result = export_document_pages(
        view,
        target,
        job,
        context=PrintDocumentContext("Well Ә-1", AppLanguage.EN),
    )

    assert result.page_count == 2
    assert [path.name for path in result.paths] == [
        "well_page_001.png",
        "well_page_002.png",
    ]
    assert all(path.read_bytes().startswith(b"\x89PNG") for path in result.paths)
    view.close()


def test_strict_export_blocks_corrupted_text(qapp, tmp_path) -> None:
    from PySide6.QtWidgets import QLabel

    widget = QLabel("Broken: \ufffd")
    widget.resize(400, 200)
    widget.show()
    qapp.processEvents()
    target = tmp_path / "broken.pdf"
    job = PrintJobSettings(output_format=PrintOutputFormat.PDF, target=target, dpi=96)

    with pytest.raises(UnicodePrintError, match="U\\+FFFD"):
        export_document_pdf(
            widget,
            target,
            job,
            context=PrintDocumentContext("Broken"),
        )
    assert not target.exists()
    widget.close()


def _paged_tablet(qapp) -> TabletView:
    dataset = Dataset(
        "dataset-multipage-print",
        "Ұңғыма Ә-1",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(100.0, 300.0, 401),
    )
    view = TabletView()
    view.resize(900, 620)
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Глубина / Тереңдік", TrackKind.DEPTH, width=120),
                TrackDefinition("gas", "Газ ΔC₁, µg/L", TrackKind.CURVE, width=420),
                TrackDefinition("text", "Описание Ә Ғ Қ", TrackKind.TEXT, width=300),
            ],
            visible_depth_top=100.0,
            visible_depth_bottom=150.0,
        )
    )
    view.set_dataset(dataset)
    view.show()
    qapp.processEvents()
    view.set_visible_depth(100.0, 150.0)
    qapp.processEvents()
    return view


def _require_system_fonts() -> None:
    if not QFontDatabase.families():
        pytest.skip("Qt offscreen backend does not expose the system font database")
