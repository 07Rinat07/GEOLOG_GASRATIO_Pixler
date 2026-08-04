from __future__ import annotations

from pathlib import Path

import fitz
import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.printing.document_export import export_document_pdf
from geoworkbench.printing.document_renderer import PrintDocumentContext
from geoworkbench.printing.page_settings import (
    PrintOrientation,
    PrintPageFormat,
    PrintPageSettings,
)
from geoworkbench.printing.pagination import PrintPaginationSettings, PrintRangeMode
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
from geoworkbench.printing.print_layout import PrintScaleMode
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
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
    phase = np.linspace(0.0, 30.0, axis.size)
    mnemonics = (
        "C1",
        "C2",
        "C3",
        "IC4",
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
            ["C1", "C2", "C3", "IC4"],
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
        (DepthDomain.TIME, 0.0, 2000.0),
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
    assert page_count >= 3
    assert density >= 0.035, (
        f"last page is visually collapsed: density={density:.4f}"
    )
    assert dense_lower_rows >= 5, (
        "the repeated form legend is missing from the lower part of the final page"
    )
