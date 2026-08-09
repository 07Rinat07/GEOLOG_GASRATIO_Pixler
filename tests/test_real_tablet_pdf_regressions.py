from __future__ import annotations

from pathlib import Path

import fitz
import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.printing.document_export import export_document_pdf
from geoworkbench.printing.auto_pagination import MAX_AUTOMATIC_PRINT_PAGE_COUNT
from geoworkbench.printing.document_renderer import (
    PrintDocumentContext,
    build_document_plan,
)
from geoworkbench.printing.page_settings import (
    PrintOrientation,
    PrintPageFormat,
    PrintPageSettings,
)
from geoworkbench.printing.pagination import PrintPaginationSettings, PrintRangeMode
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
from geoworkbench.printing.print_layout import PrintScaleMode
from geoworkbench.printing.tablet_print import capture_tablet_print_snapshot
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.header_geometry import (
    CURVE_HEADER_BOTTOM_CLEARANCE,
    CURVE_HEADER_PRINT_ROW_HEIGHT,
)
from geoworkbench.tablet.tablet_view import TabletView


def _complex_tablet(*, domain: DepthDomain, start: float, end: float) -> TabletView:
    axis = np.linspace(start, end, 1201)
    dataset = Dataset(
        f"acceptance-{domain.value}",
        f"Acceptance {domain.value}",
        DatasetKind.GTI,
        domain,
        axis,
    )
    if domain is DepthDomain.TIME:
        dataset.active_index.unit = "s"
    phase = np.linspace(0.0, 30.0, axis.size)
    mnemonics = (
        "C1",
        "C2",
        "C3",
        "IC4",
        "NC4",
        "IC5",
        "NC5",
        "TG_CALC",
        "TG_NORM_CALC",
        "C1_NORM",
        "C2_NORM",
        "C3_NORM",
        "IC4_NORM",
        "C1_REL",
        "C2_REL",
        "C3_REL",
        "C4_REL",
        "WH",
        "BH",
        "CH",
        "C1_C2",
        "C1_C3",
        "C1_C4",
        "C1_C5",
    )
    for index, mnemonic in enumerate(mnemonics, start=1):
        values = 25.0 + index + 12.0 * np.sin(phase / (2.0 + index * 0.08))
        dataset.upsert_curve(mnemonic, values, unit="%", description=mnemonic)

    tracks = [
        TrackDefinition("depth", "Глубина, m", TrackKind.DEPTH, width=60),
        TrackDefinition(
            "absolute",
            "Абсолютные компоненты",
            TrackKind.GAS,
            ["C1", "C2", "C3", "IC4", "NC4", "IC5", "NC5"],
            width=145,
        ),
        TrackDefinition(
            "sum",
            "Сумма абсолютных газов",
            TrackKind.GAS,
            ["TG_CALC"],
            width=105,
        ),
        TrackDefinition(
            "normalized-total",
            "Нормализованный суммарный газ",
            TrackKind.GAS,
            ["TG_NORM_CALC"],
            width=135,
        ),
        TrackDefinition(
            "normalized-components",
            "Нормализованные компоненты",
            TrackKind.GAS,
            ["C1_NORM", "C2_NORM", "C3_NORM", "IC4_NORM"],
            width=145,
        ),
        TrackDefinition(
            "relative",
            "Относительный газ",
            TrackKind.GAS,
            ["C1_REL", "C2_REL", "C3_REL", "C4_REL"],
            width=130,
        ),
        TrackDefinition(
            "wetness",
            "Wetness, Balance, Character и изомеры",
            TrackKind.GAS,
            ["WH", "BH", "CH"],
            width=165,
        ),
        TrackDefinition(
            "pixler",
            "Коэффициенты Pixler",
            TrackKind.GAS,
            ["C1_C2", "C1_C3", "C1_C4", "C1_C5"],
            width=145,
        ),
    ]
    view = TabletView()
    view.resize(1280, 760)
    visible_end = min(end, start + (50.0 if domain is not DepthDomain.TIME else 50.0))
    view.set_layout_and_dataset(
        TabletLayout(
            tracks,
            visible_depth_top=start,
            visible_depth_bottom=visible_end,
        ),
        dataset,
    )
    return view


def _render_last_page_metrics(pdf_path: Path) -> tuple[int, float, int]:
    with fitz.open(pdf_path) as document:
        page_count = document.page_count
        page = document[-1]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0), alpha=False)
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height,
            pixmap.width,
            pixmap.n,
        )[..., :3]
    dark = np.any(image < 245, axis=2)
    # Ignore the simple document title and footer. The tablet graph and the
    # repeated form legend must still occupy a material part of the sheet.
    body = dark[45:-45, :]
    density = float(body.mean())
    lower = body[int(body.shape[0] * 0.55) :, :]
    dense_lower_rows = int(np.count_nonzero(lower.sum(axis=1) > image.shape[1] * 0.18))
    return page_count, density, dense_lower_rows


@pytest.mark.parametrize(
    ("domain", "start", "end"),
    (
        (DepthDomain.MD, 1174.8, 1482.4),
        (DepthDomain.TIME, 0.0, 7200.0),
    ),
    ids=("las-depth", "geoscape-time"),
)
def test_complex_tablet_pdf_keeps_material_last_page_and_bottom_legend(
    qapp,
    tmp_path,
    domain: DepthDomain,
    start: float,
    end: float,
) -> None:
    tablet = _complex_tablet(domain=domain, start=start, end=end)
    tablet.show()
    qapp.processEvents()
    target = tmp_path / f"{domain.value}.pdf"
    job = PrintJobSettings(
        output_format=PrintOutputFormat.PDF,
        target=target,
        dpi=300,
        page=PrintPageSettings(
            page_format=PrintPageFormat.A4,
            orientation=PrintOrientation.LANDSCAPE,
            scale_mode=PrintScaleMode.FIT,
        ),
        pagination=PrintPaginationSettings(
            range_mode=PrintRangeMode.FULL,
            auto_units_per_page=True,
        ),
        repeat_column_header_at_bottom=True,
        strict_unicode=False,
    )
    try:
        result = export_document_pdf(
            tablet,
            target,
            job,
            context=PrintDocumentContext("Планшет"),
            overwrite=True,
        )
    finally:
        tablet.close()
        qapp.processEvents()

    page_count, density, dense_lower_rows = _render_last_page_metrics(target)
    assert result.page_count == page_count
    assert page_count >= 2
    assert density >= 0.035, (
        f"last page is visually collapsed: density={density:.4f}"
    )
    assert dense_lower_rows >= 5, (
        "the repeated form legend is missing from the lower part of the final page"
    )



def test_short_partial_snapshot_reflows_header_and_uses_one_canonical_height(
    qapp,
) -> None:
    tablet = _complex_tablet(domain=DepthDomain.MD, start=1174.8, end=1482.4)
    tablet.show()
    qapp.processEvents()
    try:
        snapshot = capture_tablet_print_snapshot(
            tablet,
            page_aspect_ratio=0.65,
            fit_columns=True,
            raster_scale=2.5,
            show_column_header=False,
            repeat_column_header_at_bottom=True,
            target_content_height=120,
            layout_content_height=900,
        )
    finally:
        tablet.close()
        qapp.processEvents()

    assert 0 < snapshot.header_height < snapshot.content_height
    absolute_header = tablet._rendered["absolute"].widget.print_curve_header_height
    assert absolute_header == (
        7 * CURVE_HEADER_PRINT_ROW_HEIGHT + CURVE_HEADER_BOTTOM_CLEARANCE
    )
    assert snapshot.header_height >= (
        absolute_header
        + tablet._rendered["absolute"].widget.natural_title_header_height
    )
    # The requested partial page has no room for the full header plus the
    # interactive 240 px plot minimum. Printing must keep only the one-pixel
    # safety body instead of letting the child plot overflow into the repeated
    # lower header crop.
    assert snapshot.content_height == snapshot.header_height + 1
    expected_pixel_height = round(snapshot.content_height * snapshot.raster_scale)
    assert all(pixmap.height() == expected_pixel_height for pixmap in snapshot.pixmaps)


def test_repeated_print_capture_does_not_accumulate_header_height(qapp) -> None:
    tablet = _complex_tablet(domain=DepthDomain.MD, start=1174.8, end=1482.4)
    tablet.show()
    qapp.processEvents()
    original_title_heights = tuple(
        item.widget.title.height() for item in tablet.printable_tracks()
    )
    original_curve_header_heights = tuple(
        item.widget.curve_header_scroll.height() for item in tablet.printable_tracks()
    )
    measurements: list[tuple[int, int]] = []
    try:
        for _ in range(5):
            snapshot = capture_tablet_print_snapshot(
                tablet,
                page_aspect_ratio=1.45,
                fit_columns=True,
                raster_scale=1.0,
                target_content_height=900,
                layout_content_height=900,
            )
            measurements.append((snapshot.header_height, snapshot.layout.total_width))
            qapp.processEvents()
        restored_title_heights = tuple(
            item.widget.title.height() for item in tablet.printable_tracks()
        )
        restored_curve_header_heights = tuple(
            item.widget.curve_header_scroll.height()
            for item in tablet.printable_tracks()
        )
    finally:
        tablet.close()
        qapp.processEvents()

    assert measurements == [measurements[0]] * len(measurements)
    assert restored_title_heights == original_title_heights
    assert restored_curve_header_heights == original_curve_header_heights


def test_full_day_time_auto_print_ignores_extreme_screen_zoom(qapp) -> None:
    tablet = _complex_tablet(domain=DepthDomain.TIME, start=0.0, end=86_400.0)
    tablet.show()
    qapp.processEvents()
    job = PrintJobSettings(
        output_format=PrintOutputFormat.PRINTER,
        page=PrintPageSettings(
            page_format=PrintPageFormat.A4,
            orientation=PrintOrientation.LANDSCAPE,
            scale_mode=PrintScaleMode.FIT,
        ),
        pagination=PrintPaginationSettings(
            range_mode=PrintRangeMode.FULL,
            auto_units_per_page=True,
        ),
        repeat_column_header_at_bottom=True,
        strict_unicode=False,
    )
    try:
        plan = build_document_plan(
            tablet,
            job,
            context=PrintDocumentContext("Планшет"),
        )
    finally:
        tablet.close()
        qapp.processEvents()

    assert plan.resolved_units_per_page is not None
    assert plan.resolved_units_per_page >= 30.0 * 60.0
    assert 1 < plan.page_count <= MAX_AUTOMATIC_PRINT_PAGE_COUNT
