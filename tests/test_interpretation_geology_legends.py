from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from geoworkbench.printing.geology_track_rendering import (
    FrozenCuttingsComponent,
    FrozenCuttingsSample,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology import (
    InterpretationGeologySnapshot,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_legend import (
    build_interpretation_geology_legend,
    geology_legend_height,
    paint_geology_legend,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import (
    CHART_HEADER_HEIGHT,
    CHART_TRACK_HEADER_HEIGHT,
    DepthPage,
    chart_geometry,
)
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.services.localization import AppLanguage


def _snapshot() -> InterpretationGeologySnapshot:
    sandstone = CatalogLithotype(
        "sandstone",
        "SS",
        "Песчаник",
        "Sandstone",
        "sedimentary",
        "#d8b26e",
        "sandstone_bricks",
        True,
        name_kk="Құмтас",
    )
    limestone = CatalogLithotype(
        "limestone",
        "LS",
        "Известняк",
        "Limestone",
        "sedimentary",
        "#c8c8b8",
        "carbonate",
        True,
        name_kk="Әктас",
    )
    return InterpretationGeologySnapshot(
        samples=(
            FrozenCuttingsSample(
                sample_id="inside",
                top_depth=1000.0,
                bottom_depth=1005.0,
                components=(FrozenCuttingsComponent("sandstone", 100.0),),
                lba_group=2,
                lba_intensity=3,
                lba_color="ГЖ",
            ),
            FrozenCuttingsSample(
                sample_id="outside",
                top_depth=1100.0,
                bottom_depth=1105.0,
                components=(FrozenCuttingsComponent("limestone", 100.0),),
                lba_group=5,
                lba_intensity=5,
                lba_color="Ч",
            ),
        ),
        lithotypes=(sandstone, limestone),
    )


def test_dynamic_geology_legend_contains_only_symbols_used_in_report_interval() -> None:
    legend = build_interpretation_geology_legend(
        _snapshot(),
        999.0,
        1010.0,
        AppLanguage.RU,
    )

    codes = {item.code for item in legend.items}
    assert {"SS", "МБ", "3", "ГЖ"} <= codes
    assert "LS" not in codes
    assert "САБ" not in codes
    assert "5" not in codes
    assert "Ч" not in codes


def test_dynamic_geology_legend_respects_visible_track_selection() -> None:
    cuttings_only = build_interpretation_geology_legend(
        _snapshot(),
        999.0,
        1010.0,
        AppLanguage.RU,
        include_cuttings=True,
        include_lba=False,
    )
    lba_only = build_interpretation_geology_legend(
        _snapshot(),
        999.0,
        1010.0,
        AppLanguage.RU,
        include_cuttings=False,
        include_lba=True,
    )

    assert {item.kind for item in cuttings_only.items} == {"lithology"}
    assert "lithology" not in {item.kind for item in lba_only.items}
    assert {"lba-type", "lba-intensity", "lba-color"} <= {
        item.kind for item in lba_only.items
    }


def test_dynamic_geology_legend_localizes_actual_items() -> None:
    legend = build_interpretation_geology_legend(
        _snapshot(),
        999.0,
        1010.0,
        AppLanguage.EN,
    )
    labels = {item.code: item.label for item in legend.items}

    assert labels["SS"] == "Sandstone"
    assert labels["МБ"] == "oily bitumen"
    assert labels["3"] == "thin continuous ring"
    assert labels["ГЖ"] == "bluish yellow"


def test_geology_legend_painter_uses_pattern_and_marker_contracts(qapp) -> None:
    legend = build_interpretation_geology_legend(
        _snapshot(),
        999.0,
        1010.0,
        AppLanguage.RU,
    )
    height = geology_legend_height(600.0, legend)
    image = QImage(600, int(height) + 4, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    try:
        paint_geology_legend(
            painter,
            QRectF(0.0, 0.0, 600.0, height),
            legend,
            AppLanguage.RU,
        )
    finally:
        painter.end()

    non_white = 0
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).name() != "#ffffff":
                non_white += 1
                if non_white > 20:
                    break
        if non_white > 20:
            break
    assert non_white > 20


def test_pdf_geometry_reserves_top_and_repeat_geology_legends() -> None:
    content = QRectF(0.0, 0.0, 600.0, 800.0)
    page = DepthPage(1000.0, 1100.0, 500, 400.0)

    geometry = chart_geometry(
        content,
        page,
        3,
        geology_track_count=2,
        geology_legend_height=54.0,
        geology_repeat_legend_height=28.0,
    )

    assert geometry.geology_legend_rect is not None
    assert geometry.geology_repeat_legend_rect is not None
    assert geometry.geology_legend_rect.height() == 54.0
    assert geometry.left_axis_rect.top() == (
        CHART_HEADER_HEIGHT + 54.0 + CHART_TRACK_HEADER_HEIGHT
    )
    assert geometry.geology_repeat_legend_rect.top() > geometry.plot_rect.bottom()
    assert geometry.geology_repeat_legend_rect.bottom() <= geometry.note_rect.top()
