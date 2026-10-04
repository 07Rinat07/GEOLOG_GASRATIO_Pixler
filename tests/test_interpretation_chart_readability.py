from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFontMetricsF, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart as base_chart
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as chart
from geoworkbench.printing.geology_track_rendering import FrozenCuttingsComponent, FrozenCuttingsSample
from geoworkbench.printing.hydrocarbon_interpretation_geology import InterpretationGeologySnapshot
from geoworkbench.printing.hydrocarbon_interpretation_geology_legend import (
    build_interpretation_geology_legend,
    geology_legend_height,
    paint_geology_legend,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    GeologyTrackVisibility,
    InterpretationGeologyTrackSettings,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.interpretation_chart_key import interpretation_chart_key_html
from geoworkbench.printing.interpretation_track_headings import HEADING_FLAGS
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.services.lba_standard import lba_groups_for_color
from geoworkbench.services.localization import AppLanguage


def _dataset() -> Dataset:
    depth = np.linspace(1000.0, 1350.0, 351)
    dataset = Dataset("readability", "Readability", DatasetKind.GTI, DepthDomain.MD, depth)
    for name in ("TG_CALC", "TG_NORM_CALC", "WH", "BH", "CH", "C1_C2", "DEXP",
                 "OPUS3", "OPUS4", "OPUS_TG_PCT",
                 "OPUS_GM_1", "OPUS_GM_2", "OPUS_GM_3"):
        dataset.curves[name] = CurveData(
            CurveMetadata(name, name, name, "ratio", name, dataset.dataset_id),
            np.linspace(1.0, 2.0, len(depth)),
        )
    return dataset


def _report(profile: str = "standard"):
    return SimpleNamespace(
        report_profile=profile, primary_mnemonic="TG_CALC", methods=(), candidates=(),
        depth_unit="m", opus_gasomer=None,
    )


def _geology() -> InterpretationGeologySnapshot:
    return InterpretationGeologySnapshot(
        samples=(
            FrozenCuttingsSample("a", 1000.0, 1150.0,
                                 (FrozenCuttingsComponent("sandstone", 100.0),),
                                 lba_group=1, lba_intensity=1, lba_color="БГ"),
            FrozenCuttingsSample("b", 1150.0, 1250.0, (),
                                 lba_group=1, lba_intensity=2, lba_color="БЖ"),
            FrozenCuttingsSample("c", 1250.0, 1350.0, (),
                                 lba_group=2, lba_intensity=2, lba_color="СЖ"),
        ),
        lithotypes=(CatalogLithotype(
            "sandstone", "SS", "Песчаник", "Sandstone", "sedimentary", "#d8b26e",
            "sandstone_bricks", True, name_kk="Құмтас",
        ),),
    )


def _normalized(text: str) -> str:
    return "".join(text.split())


def test_lba_legend_order_does_not_depend_on_sample_encounter_order() -> None:
    geology = _geology()
    forward = build_interpretation_geology_legend(geology, 1000.0, 1350.0, AppLanguage.RU)
    reverse = build_interpretation_geology_legend(
        replace(geology, samples=tuple(reversed(geology.samples))),
        1000.0, 1350.0, AppLanguage.RU,
    )
    assert forward == reverse
    assert [item.kind for item in forward.items] == [
        "lithology", "lba-type", "lba-type", "lba-intensity", "lba-intensity",
        "lba-color", "lba-color", "lba-color",
    ]
    assert next(item.label for item in forward.items if item.code == "СЖ") == "светло-жёлтый"
    assert lba_groups_for_color("СЖ") == ()


@pytest.mark.parametrize("compact", [False, True])
def test_repeat_legend_decodes_all_screenshot_codes(qapp, tmp_path, compact):
    legend = build_interpretation_geology_legend(_geology(), 1000.0, 1350.0, AppLanguage.RU)
    output = tmp_path / "legend.pdf"
    writer = QPdfWriter(str(output))
    writer.setResolution(72)
    painter = QPainter(writer)
    try:
        height = geology_legend_height(500.0, legend, compact=compact, paint_device=writer)
        paint_geology_legend(painter, QRectF(0, 0, 500, height), legend,
                            AppLanguage.RU, compact=compact)
    finally:
        painter.end()
    with fitz.open(output) as document:
        text = _normalized(document[0].get_text())
    for item in legend.items:
        assert _normalized(f"{item.code} — {item.label}") in text
    for title in ("Литология", "ЛБА: тип битумоида", "ЛБА: интенсивность",
                  "ЛБА: цвет флуоресценции"):
        assert _normalized(title) in text


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("landscape", [False, True])
@pytest.mark.parametrize("tracks", ["none", "lba", "both"])
@pytest.mark.parametrize("profile", ["standard", "opus"])
def test_pdf_headers_fit_and_legends_repeat_above_plot(
    qapp, tmp_path, monkeypatch, language, landscape, tracks, profile,
):
    output = tmp_path / "charts.pdf"
    writer = QPdfWriter(str(output))
    writer.setResolution(72)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape if landscape
                              else QPageLayout.Orientation.Portrait)
    observed = []
    draw_page = chart._draw_chart_page

    def capture(painter, geometry, *args):
        observed.append(geometry)
        return draw_page(painter, geometry, *args)

    monkeypatch.setattr(chart, "_draw_chart_page", capture)
    settings = InterpretationGeologyTrackSettings(
        cuttings=GeologyTrackVisibility.SHOW if tracks == "both" else GeologyTrackVisibility.HIDE,
        lba=GeologyTrackVisibility.SHOW if tracks != "none" else GeologyTrackVisibility.HIDE,
    )
    painter = QPainter(writer)
    try:
        canvas = PageCanvas(writer, painter, language)
        chart.render_chart_pages(canvas, _report(profile), _dataset(), language,
                                 geology=_geology(), geology_track_settings=settings)
    finally:
        painter.end()
    assert len(observed) > 1
    legend = build_interpretation_geology_legend(
        _geology(), 1000.0, 1350.0, language,
        include_cuttings=tracks == "both", include_lba=tracks != "none",
    )
    with fitz.open(output) as document:
        assert len(document) == len(observed)
        for page, geometry in zip(document, observed, strict=True):
            text = _normalized(page.get_text())
            for name, _curves in base_chart._panel_curves(_report(profile), _dataset()):
                assert _normalized(base_chart._labels(language)[name]) in text
            for item in legend.items:
                assert _normalized(f"{item.code} — {item.label}") in text
            assert geometry.geology_repeat_legend_rect is None
            if not legend.empty:
                assert geometry.geology_legend_rect is not None
                assert geometry.geology_legend_rect.bottom() <= (
                    geometry.plot_rect.top() - geometry.track_header_height
                )
            assert geometry.plot_rect.height() >= 112.0
            assert geometry.legend_rect.bottom() <= geometry.note_rect.top()
    assert len({geometry.plot_rect.top() for geometry in observed}) == 1


@pytest.mark.parametrize("dpi", [72, 96, 144, 192])
def test_heading_wrap_reserves_complete_text_at_destination_dpi(qapp, dpi):
    from geoworkbench.printing.interpretation_track_headings import track_heading_height

    image = QImage(600, 300, QImage.Format.Format_ARGB32_Premultiplied)
    image.setDotsPerMeterX(round(dpi / 0.0254))
    image.setDotsPerMeterY(round(dpi / 0.0254))
    title = "Общий и нормализованный газ"
    height = track_heading_height(title, 90.0, 7.5, image)
    font = print_font(7.5, text=title, bold=True)
    bounds = QFontMetricsF(font, image).boundingRect(
        QRectF(0, 0, 86.0, height), int(HEADING_FLAGS), title,
    )
    assert bounds.height() <= height - 4.0
    assert bounds.width() <= 86.0
    assert height > QFontMetricsF(font, image).height()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_chart_key_uses_actual_parameters_and_sourced_haworth_formulas(language):
    from geoworkbench.calculations.pixler import build_all_sourced_formula_registry

    html = interpretation_chart_key_html(_report(), _dataset(), language)
    for profile in build_all_sourced_formula_registry().available():
        if profile.output_mnemonic in {"WH", "BH", "CH", "C1_C2", "DEXP"}:
            assert profile.expression in html
    assert "Wh" in html and "Bh" in html
    assert "OPUS_GM" not in html
    assert "&lt;" not in html


def test_opus_chart_key_keeps_component_sum_basis_separate_from_gasomer() -> None:
    report = _report("opus")
    report.opus_gasomer = SimpleNamespace(formulas=(("OPUS_GM_1", "different gasomer basis"),))
    html = interpretation_chart_key_html(report, _dataset(), AppLanguage.RU)
    assert "OPUS3 = (p1 * p2) / (p2 + p3)^2" in html
    assert "OPUS4 = (p1 * p2 * p3) / (p2 + p3 + p4)^3" in html
    assert "pi = 100 × Ci / Σ(C1…C5)" in html
    assert "different gasomer basis" not in html


def test_full_pdf_separates_lithology_legend_and_method_key_before_charts(qapp, tmp_path):
    from geoworkbench.printing.hydrocarbon_interpretation_report import (
        export_hydrocarbon_interpretation_pdf,
    )
    from geoworkbench.project.session import ProjectSession
    from geoworkbench.services.hydrocarbon_interpretation import (
        build_hydrocarbon_interpretation_report,
    )

    dataset = _dataset()
    dataset.curves = {name: curve for name, curve in dataset.curves.items()
                      if name in {"TG_CALC", "WH", "BH", "CH", "C1_C2"}}
    original = {name: curve.values.copy() for name, curve in dataset.curves.items()}
    session = ProjectSession()
    session.add_dataset(dataset)
    report = build_hydrocarbon_interpretation_report(session)
    target = tmp_path / "complete.pdf"
    export_hydrocarbon_interpretation_pdf(report, target, dataset=dataset, include_chart=True,
                                         geology=_geology())
    with fitz.open(target) as document:
        page_texts = [page.get_text() for page in document]
        key_page_index = next(
            index for index, page_text in enumerate(page_texts)
            if "Пояснения к графикам" in page_text
        )
        key_text = page_texts[key_page_index]
        legend_page_index = next(
            index for index, page_text in enumerate(page_texts)
            if "Литология" in page_text
        )
        assert legend_page_index < key_page_index
        assert "Литология" not in key_text
        assert "Wh = 100" in key_text
        assert "Bh =" in key_text and "Ch =" in key_text
        chart_page_index = next(
            index for index, page_text in enumerate(page_texts)
            if "Графики интерпретационных кривых" in page_text
        )
        assert key_page_index < chart_page_index
    for name, values in original.items():
        np.testing.assert_array_equal(values, dataset.curves[name].values)
