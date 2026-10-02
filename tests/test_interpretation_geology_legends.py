from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFontMetricsF, QImage, QPainter

from geoworkbench.printing.geology_track_rendering import (
    FrozenCuttingsComponent,
    FrozenCuttingsSample,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology import (
    InterpretationGeologySnapshot,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_legend import (
    GeologyLegendItem,
    InterpretationGeologyLegend,
    build_interpretation_geology_legend,
    geology_legend_height,
    paint_geology_legend,
    paginate_geology_legend,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import (
    CHART_HEADER_HEIGHT,
    CHART_TRACK_HEADER_HEIGHT,
    DepthPage,
    chart_geometry,
)
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.services.localization import AppLanguage
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.printing import hydrocarbon_interpretation_geology_legend as legend_renderer


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



def test_dynamic_geology_legend_keeps_unresolved_lba_marker_explicit() -> None:
    geology = InterpretationGeologySnapshot(
        samples=(
            FrozenCuttingsSample(
                sample_id="unknown-lba",
                top_depth=1000.0,
                bottom_depth=1005.0,
                components=(),
                lba_description="visible fluorescence without normalized type",
            ),
        ),
        lithotypes=(),
    )

    legend = build_interpretation_geology_legend(
        geology,
        999.0,
        1010.0,
        AppLanguage.EN,
        include_cuttings=False,
        include_lba=True,
    )

    unknown = [item for item in legend.items if item.kind == "lba-type"]
    assert len(unknown) == 1
    assert unknown[0].code == "?"
    assert unknown[0].key == "unknown"
    assert unknown[0].label == "unresolved bitumen"
    assert unknown[0].intensity is None



def test_long_geology_labels_expand_full_legend_height(qapp) -> None:
    short = InterpretationGeologyLegend(
        (
            GeologyLegendItem(
                "lithology",
                "short",
                "SS",
                "Sandstone",
                "#d8b26e",
                "sandstone_bricks",
            ),
        )
    )
    long = InterpretationGeologyLegend(
        (
            GeologyLegendItem(
                "lithology",
                "long",
                "SS",
                (
                    "Очень длинное локализованное наименование литологии, "
                    "которое должно переноситься на несколько строк без обрезания"
                ),
                "#d8b26e",
                "sandstone_bricks",
            ),
        )
    )

    short_height = geology_legend_height(150.0, short)
    long_height = geology_legend_height(150.0, long)

    assert short_height >= 48.0
    assert long_height > short_height


def test_geology_legend_remains_distinguishable_after_grayscale_conversion(qapp) -> None:
    legend = InterpretationGeologyLegend(
        (
            GeologyLegendItem(
                "lithology",
                "sandstone",
                "SS",
                "Песчаник",
                "#d8b26e",
                "sandstone_bricks",
            ),
            GeologyLegendItem(
                "lba-type",
                "oily-bitumen",
                "МБ",
                "маслянистый битум",
                "#f59e0b",
                intensity=3,
            ),
        )
    )
    width = 360.0
    height = geology_legend_height(width, legend)
    image = QImage(
        int(width),
        int(height) + 2,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    try:
        paint_geology_legend(
            painter,
            QRectF(0.0, 0.0, width, height),
            legend,
            AppLanguage.RU,
        )
    finally:
        painter.end()

    gray = image.convertToFormat(QImage.Format.Format_Grayscale8)
    values = {
        gray.pixelColor(x, y).red()
        for y in range(gray.height())
        for x in range(gray.width())
    }

    assert len(values) >= 4
    assert min(values) < 100
    assert max(values) > 240


def test_multi_page_geology_layout_uses_full_then_compact_legend_exclusively() -> None:
    content = QRectF(0.0, 0.0, 600.0, 800.0)
    first_page = DepthPage(1000.0, 1100.0, 500, 400.0)
    continuation = DepthPage(1100.0, 1200.0, 500, 400.0)

    first = chart_geometry(
        content,
        first_page,
        3,
        geology_track_count=2,
        geology_legend_height=62.0,
        geology_repeat_legend_height=0.0,
    )
    later = chart_geometry(
        content,
        continuation,
        3,
        geology_track_count=2,
        geology_legend_height=0.0,
        geology_repeat_legend_height=28.0,
    )

    assert first.geology_legend_rect is not None
    assert first.geology_repeat_legend_rect is None
    assert later.geology_legend_rect is None
    assert later.geology_repeat_legend_rect is not None
    assert first.left_axis_rect.top() > later.left_axis_rect.top()
    assert later.geology_repeat_legend_rect.bottom() <= later.note_rect.top()


@pytest.mark.parametrize("dpi", [72, 96, 144, 192])
@pytest.mark.parametrize("label", [
    "Очень длинное название известняка с вкраплениями пирита " * 8,
    "Пирит түйіршіктері бар әктастың өте ұзын атауы " * 8,
    "A very long limestone name with disseminated pyrite " * 8,
])
def test_legend_uses_destination_metrics_and_explicit_ellipsis(qapp, dpi, label) -> None:
    image = QImage(320, 200, QImage.Format.Format_ARGB32_Premultiplied)
    image.setDotsPerMeterX(round(dpi / 0.0254))
    image.setDotsPerMeterY(round(dpi / 0.0254))
    text = f"LS — {label}"
    font = print_font(6.6, text=text)
    metrics = QFontMetricsF(font, image)
    legend = InterpretationGeologyLegend((
        GeologyLegendItem("lithology", "limestone", "LS", label),
    ))
    width = 150.0
    measured = metrics.boundingRect(
        QRectF(0.0, 0.0, width - 25.0, 1000.0),
        int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft), text,
    ).height()
    height = geology_legend_height(width, legend, paint_device=image)
    assert height == pytest.approx(26.0 + min(64.0, max(22.0, measured + 4.0)))
    fitted = legend_renderer._fit_legend_text(text, metrics, width - 25.0, height - 28.0)
    assert fitted.endswith("…")
    assert len(fitted) < len(text)
    bounds = metrics.boundingRect(
        QRectF(0.0, 0.0, width - 25.0, height - 28.0),
        int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft), fitted,
    )
    assert bounds.height() <= height - 28.0
    assert bounds.width() <= width - 25.0


def test_overflow_legend_pagination_preserves_all_symbols_in_order(qapp) -> None:
    device = QImage(800, 600, QImage.Format.Format_ARGB32_Premultiplied)
    items = tuple(
        GeologyLegendItem("lithology", str(index), f"R{index}", "Длинное имя " * 40)
        for index in range(103)
    )
    legend = InterpretationGeologyLegend(items)
    pages = paginate_geology_legend(760.0, legend, 480.0, paint_device=device)
    assert len(pages) > 1
    assert tuple(item for page in pages for item in page.items) == items
    assert all(
        geology_legend_height(760.0, page, paint_device=device) <= 480.0
        for page in pages
    )
    assert legend.items == items
