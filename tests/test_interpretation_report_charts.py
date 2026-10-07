from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.printing.hydrocarbon_interpretation_chart import (
    _draw_panel,
    _panel_curves as whole_well_panels,
    hydrocarbon_interpretation_chart_data_uri,
)
from geoworkbench.printing.hydrocarbon_interpretation_chart_front import (
    hydrocarbon_interpretation_html_with_front_chart,
)
from geoworkbench.printing.hydrocarbon_interpretation_curve_labels import (
    curve_display_name,
    curve_legend_text,
    report_curve_label_hints,
)
from geoworkbench.printing.interpretation_chart_key import (
    interpretation_chart_key_html,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_chart import (
    _curve_ranges,
    _draw_candidate_bands,
    _draw_curves,
    _panel_curves as printed_panels,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import DepthPage
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    export_hydrocarbon_interpretation_pdf,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.gas_curve_presentation import (
    GAS_PRINT_POINT_RADIUS_PT,
    GAS_SCATTER_VERTICAL_SPACING,
    gas_scatter_point_budget,
)
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonCandidateInterval,
    build_hydrocarbon_interpretation_report,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace


def _session_with_report_curves(
    *,
    depth_start: float = 1_300.0,
    depth_span: float = 120.0,
    samples: int = 241,
) -> ProjectSession:
    depth = np.linspace(depth_start, depth_start + depth_span, samples)
    center = depth_start + depth_span * 0.55
    width = max(1.0, depth_span * 0.06)
    dataset = Dataset(
        "dataset",
        "Geology and technology",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    series = {
        "TG_CALC": 0.02 + 0.08 * np.exp(-((depth - center) / width) ** 2),
        "WH": 5.0 + 20.0 * np.exp(-((depth - center) / (width * 1.3)) ** 2),
        "BH": 2.0 + 8.0 * np.exp(-((depth - center) / (width * 1.5)) ** 2),
        "CH": 0.5 + 2.0 * np.exp(-((depth - center) / (width * 1.2)) ** 2),
        "C1_C2": 4.0 + 2.0 * np.sin(depth / 9.0),
        "C1_C3": 12.0 + 5.0 * np.cos(depth / 11.0),
        "DEXP": 1.1 + 0.2 * np.sin(depth / 13.0),
    }
    for index, (mnemonic, values) in enumerate(series.items()):
        dataset.curves[f"curve-{index}"] = CurveData(
            CurveMetadata(
                f"curve-{index}",
                mnemonic,
                mnemonic,
                "",
                "test",
                dataset.dataset_id,
            ),
            np.asarray(values, dtype=np.float64),
        )
    session = ProjectSession()
    session.add_dataset(dataset, "Well 494")
    return session


def _pdf_page_count(payload: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", payload))


def test_chart_explanations_omit_acquisition_context_rows() -> None:
    depth = np.linspace(100.0, 104.0, 5)
    dataset = Dataset(
        "key-filter",
        "Chart key filter",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    for mnemonic, values in {
        "ROP": np.linspace(8.0, 12.0, depth.size),
        "FLOW_IN": np.linspace(30.0, 34.0, depth.size),
        "FLOW_OUT": np.linspace(29.0, 33.0, depth.size),
        "TG_CALC": np.linspace(0.1, 0.5, depth.size),
        "TG": np.linspace(0.2, 0.6, depth.size),
        "WH": np.linspace(10.0, 20.0, depth.size),
        "BH": np.linspace(2.0, 4.0, depth.size),
        "CH": np.linspace(0.5, 1.5, depth.size),
        "C1_C2": np.linspace(3.0, 6.0, depth.size),
    }.items():
        dataset.upsert_curve(mnemonic, values)

    report = SimpleNamespace(
        primary_mnemonic="TG_CALC|TG",
        report_profile="standard",
        methods=(),
    )
    html = interpretation_chart_key_html(
        report,  # type: ignore[arg-type]
        dataset,
        AppLanguage.RU,
    )

    for unwanted in (
        "Скорость бур.",
        "Расх. на вх.",
        "Расх на вх.",
        "Расх. на вых.",
        "Общий газ",
        "Сод. горюч.газ.",
    ):
        assert unwanted not in html

    assert "Влажность Haworth" in html
    assert "Баланс Haworth" in html
    assert "Характер Haworth" in html
    assert "Отношение C1/C2" in html


def test_printed_chart_scales_each_page_and_exposes_missing_measurements() -> None:
    depth = np.linspace(0.0, 199.0, 200)
    dataset = Dataset("page-ranges", "Page ranges", DatasetKind.GTI, DepthDomain.MD, depth)
    values = np.concatenate(
        (np.linspace(1.0, 2.0, 100), np.linspace(100.0, 200.0, 80), np.full(20, np.nan))
    )
    curve = CurveData(
        CurveMetadata("gas", "TG_CALC", "TG_CALC", "%", None, dataset.dataset_id),
        values,
    )
    dataset.curves["gas"] = curve
    panels = (("total", (curve,)),)

    first = _curve_ranges(panels, dataset, page=DepthPage(0.0, 99.0, 500, 500.0))
    second = _curve_ranges(panels, dataset, page=DepthPage(100.0, 179.0, 500, 500.0))
    missing = _curve_ranges(panels, dataset, page=DepthPage(180.0, 199.0, 500, 500.0))

    assert first["gas"][1] < 2.1
    assert second["gas"][0] > 100.0
    assert missing == {}


def test_report_charts_keep_source_named_las_evidence() -> None:
    dataset = Dataset(
        "source-names", "Source names", DatasetKind.GTI, DepthDomain.MD,
        np.linspace(100.0, 150.0, 51),
    )
    for mnemonic, canonical in (("S1500", "S1500"), ("S224", "S224"), ("S1600", "TG")):
        dataset.curves[mnemonic] = CurveData(
            CurveMetadata(mnemonic, mnemonic, canonical, "%", None, dataset.dataset_id),
            np.linspace(1.0, 2.0, 51),
        )
    report = SimpleNamespace(
        primary_mnemonic="S1500", report_profile="standard",
        methods=(SimpleNamespace(curve_mnemonics=("DEXP",), available_mnemonics=("S224",)),),
    )

    for select in (printed_panels, whole_well_panels):
        panels = dict(select(report, dataset))
        assert {curve.metadata.original_mnemonic for curve in panels["total"]} == {
            "S1500", "S1600"
        }
        assert [curve.metadata.original_mnemonic for curve in panels["drilling"]] == ["S224"]


def test_pdf_curve_renderer_keeps_explicit_scatter_primitive_and_line_primitive() -> None:
    class RecordingPainter:
        def __init__(self) -> None:
            self.lines = 0
            self.ellipses = 0
            self.ellipse_rects: list[QRectF] = []

        def save(self) -> None:
            pass

        def restore(self) -> None:
            pass

        def setClipRect(self, _rect) -> None:
            pass

        def setPen(self, _pen) -> None:
            pass

        def setBrush(self, _brush) -> None:
            pass

        def drawLine(self, _line) -> None:
            self.lines += 1

        def drawEllipse(self, rect) -> None:
            self.ellipses += 1
            self.ellipse_rects.append(QRectF(rect))

    depth = np.linspace(100.0, 104.0, 5)
    dataset = Dataset(
        "scatter-report",
        "Scatter report",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    ratio = CurveData(
        CurveMetadata(
            "ratio",
            "PIXLER_C1_C2",
            "PIXLER_C1_C2",
            "ratio",
            None,
            dataset.dataset_id,
        ),
        np.linspace(1.5, 3.5, 5),
    )
    total_gas = CurveData(
        CurveMetadata("gas", "TG_CALC", "TG_CALC", "%", None, dataset.dataset_id),
        np.linspace(1.0, 5.0, 5),
    )
    drilling = CurveData(
        CurveMetadata("rop", "ROP", "ROP", "m/h", None, dataset.dataset_id),
        np.linspace(10.0, 14.0, 5),
    )
    page = DepthPage(100.0, 104.0, 100, 100.0)
    rect = QRectF(0.0, 0.0, 100.0, 100.0)

    ratio_painter = RecordingPainter()
    _draw_curves(
        ratio_painter,  # type: ignore[arg-type]
        rect,
        page,
        dataset,
        (ratio,),
        {"ratio": (1.5, 3.5)},
        point_series=True,
    )
    assert ratio_painter.ellipses > 0
    assert ratio_painter.lines == 0
    assert ratio_painter.ellipse_rects
    expected_diameter = GAS_PRINT_POINT_RADIUS_PT * 2.0
    assert all(
        rect.width() == expected_diameter and rect.height() == expected_diameter
        for rect in ratio_painter.ellipse_rects
    )

    for curve, value_range in (
        (total_gas, {"gas": (1.0, 5.0)}),
        (drilling, {"rop": (10.0, 14.0)}),
    ):
        line_painter = RecordingPainter()
        _draw_curves(
            line_painter,  # type: ignore[arg-type]
            rect,
            page,
            dataset,
            (curve,),
            value_range,
            point_series=False,
        )
        assert line_painter.lines > 0
        assert line_painter.ellipses == 0


def test_singleton_ratio_observation_survives_preview_and_pdf_range(qapp) -> None:
    class RecordingPainter:
        def __init__(self) -> None:
            self.ellipses = 0

        def drawEllipse(self, *_args) -> None:
            self.ellipses += 1

        def __getattr__(self, _name):
            return lambda *args, **kwargs: None

    depth = np.asarray([100.0, 101.0, 102.0], dtype=np.float64)
    finite_depth = np.isfinite(depth)
    dataset = Dataset(
        "singleton-ratio",
        "Singleton ratio",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    ratio = CurveData(
        CurveMetadata(
            "ratio",
            "C1_C2",
            "C1_C2",
            "ratio",
            None,
            dataset.dataset_id,
        ),
        np.asarray([np.nan, 2.5, np.nan], dtype=np.float64),
    )
    total = CurveData(
        CurveMetadata(
            "total",
            "TG_CALC",
            "TG_CALC",
            "%",
            None,
            dataset.dataset_id,
        ),
        np.asarray([np.nan, 7.0, np.nan], dtype=np.float64),
    )
    dataset.curves[ratio.metadata.curve_id] = ratio
    dataset.curves[total.metadata.curve_id] = total
    report = SimpleNamespace(
        primary_mnemonic="",
        report_profile="standard",
        methods=(),
    )

    whole_panels = dict(whole_well_panels(report, dataset))
    printed = dict(printed_panels(report, dataset))
    assert whole_panels["ratios"] == (ratio,)
    assert printed["ratios"] == (ratio,)
    assert whole_panels["total"] == ()
    assert printed["total"] == ()

    preview = RecordingPainter()
    _draw_panel(
        preview,  # type: ignore[arg-type]
        QRectF(0.0, 0.0, 120.0, 180.0),
        depth,
        finite_depth,
        100.0,
        102.0,
        "ratios",
        whole_panels["ratios"],
        (),
        AppLanguage.RU,
        {},
    )
    # A singleton cannot form a line, so it remains as one factual marker.
    assert preview.ellipses == 1

    page = DepthPage(100.0, 102.0, 100, 100.0)
    ranges = _curve_ranges(
        (("ratios", printed["ratios"]), ("total", printed["total"])),
        dataset,
        page=page,
    )
    assert "ratio" in ranges
    assert ranges["ratio"][0] < 2.5 < ranges["ratio"][1]
    assert "total" not in ranges

    pdf_painter = RecordingPainter()
    _draw_curves(
        pdf_painter,  # type: ignore[arg-type]
        QRectF(0.0, 0.0, 120.0, 180.0),
        page,
        dataset,
        printed["ratios"],
        {"ratio": ranges["ratio"]},
        point_series=True,
    )
    assert pdf_painter.ellipses == 1

def test_report_panel_selector_keeps_singleton_opus_series() -> None:
    depth = np.asarray([100.0, 101.0, 102.0], dtype=np.float64)
    dataset = Dataset(
        "singleton-opus",
        "Singleton OPUS",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    opus = CurveData(
        CurveMetadata(
            "opus",
            "OPUS3",
            "OPUS3",
            "ratio",
            None,
            dataset.dataset_id,
        ),
        np.asarray([np.nan, 1.25, np.nan], dtype=np.float64),
    )
    dataset.curves[opus.metadata.curve_id] = opus
    report = SimpleNamespace(
        primary_mnemonic="",
        report_profile="opus",
        methods=(),
    )

    for select in (whole_well_panels, printed_panels):
        panels = dict(select(report, dataset))
        assert panels["opus"] == (opus,)


@pytest.mark.parametrize("gap_value", [None, np.nan, 0.0, -1.0])
def test_sparse_ratio_observation_survives_continuous_preview_downsampling(qapp, gap_value) -> None:
    class RecordingPainter:
        def __init__(self) -> None:
            self.ellipses = 0
            self.curve_lines = 0

        def drawLine(self, line) -> None:
            if line.x1() != line.x2() and line.y1() != line.y2():
                self.curve_lines += 1

        def drawEllipse(self, *_args) -> None:
            self.ellipses += 1

        def __getattr__(self, _name):
            return lambda *args, **kwargs: None

    depth = np.arange(3_601, dtype=np.float64)
    values = np.full(depth.shape, np.nan, dtype=np.float64)
    # Index 1235 is intentionally absent from the old 1,800-point uniform
    # depth sample, so this guards against losing factual sparse observations.
    values[1_235] = 2.5
    if gap_value is not None:
        values[1_236] = gap_value
        values[1_237] = 3.0
    dataset = Dataset(
        "sparse-ratio-preview",
        "Sparse ratio preview",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    ratio = CurveData(
        CurveMetadata(
            "ratio",
            "C1_C2",
            "C1_C2",
            "ratio",
            None,
            dataset.dataset_id,
        ),
        values,
    )
    dataset.curves[ratio.metadata.curve_id] = ratio
    report = SimpleNamespace(
        primary_mnemonic="",
        report_profile="standard",
        methods=(),
    )
    selected = dict(whole_well_panels(report, dataset))["ratios"]
    assert selected == (ratio,)

    painter = RecordingPainter()
    _draw_panel(
        painter,  # type: ignore[arg-type]
        QRectF(0.0, 0.0, 120.0, 180.0),
        depth,
        np.isfinite(depth),
        float(depth[0]),
        float(depth[-1]),
        "ratios",
        selected,
        (),
        AppLanguage.RU,
        {},
    )

    # Isolated factual observations stay visible even though dense ratios use lines.
    assert painter.ellipses == (1 if gap_value is None else 2)
    assert painter.curve_lines == 0


def test_dense_ratio_preview_uses_bounded_continuous_line_geometry(qapp) -> None:
    class RecordingPainter:
        def __init__(self) -> None:
            self.ellipses = 0
            self.lines = 0

        def drawEllipse(self, *_args) -> None:
            self.ellipses += 1

        def drawLine(self, *_args) -> None:
            self.lines += 1

        def drawPolyline(self, points) -> None:
            self.lines += max(0, points.size() - 1)

        def __getattr__(self, _name):
            return lambda *args, **kwargs: None

    depth = np.arange(3_601, dtype=np.float64)
    dataset = Dataset(
        "dense-ratio-preview",
        "Dense ratio preview",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    ratio = CurveData(
        CurveMetadata(
            "ratio",
            "C1_C2",
            "C1_C2",
            "ratio",
            None,
            dataset.dataset_id,
        ),
        np.linspace(1.0, 40.0, depth.size, dtype=np.float64),
    )

    painter = RecordingPainter()
    rect = QRectF(0.0, 0.0, 120.0, 180.0)
    _draw_panel(
        painter,  # type: ignore[arg-type]
        rect,
        depth,
        np.isfinite(depth),
        float(depth[0]),
        float(depth[-1]),
        "ratios",
        (ratio,),
        (),
        AppLanguage.RU,
        {},
    )

    # The factual profile is a line, not a cloud. Sampling is bounded by the
    # preview-height budget while retaining enough vertices for the real trend.
    assert painter.lines > 100
    assert painter.lines < 2_000
    assert painter.ellipses == 0

def test_standard_pdf_candidate_band_keeps_shape_and_code_for_grayscale() -> None:
    class RecordingPainter:
        def __init__(self) -> None:
            self.fills = 0
            self.ellipses = 0
            self.texts: list[str] = []

        def fillRect(self, *_args) -> None:
            self.fills += 1

        def drawEllipse(self, *_args) -> None:
            self.ellipses += 1

        def drawText(self, *args) -> None:
            self.texts.append(str(args[-1]))

        def __getattr__(self, _name):
            return lambda *args, **kwargs: None

    candidate = HydrocarbonCandidateInterval(
        top_depth=120.0,
        bottom_depth=130.0,
        sample_count=11,
        anomaly_strength="strong",
        primary_mnemonic="TG",
        max_robust_z=4.0,
        max_primary_value=2.0,
        fluid_hypothesis="probable_gas",
        interval_wetness=None,
        background_wetness=None,
        wetness_robust_z=None,
        interval_balance=None,
        interval_character=None,
        pixler_assessment=None,
        lba_assessments=(),
        gas_lba_correlation="",
        metrics=(),
        evidence=(),
    )
    painter = RecordingPainter()
    rect = QRectF(0.0, 0.0, 120.0, 180.0)
    page = DepthPage(100.0, 150.0, 100, 100.0)

    _draw_candidate_bands(
        painter,  # type: ignore[arg-type]
        rect,
        page,
        (candidate,),
        show_codes=True,
    )

    assert painter.fills == 1
    assert painter.ellipses == 1
    assert "G" in painter.texts


def test_dense_ratio_pdf_scatter_is_density_bounded() -> None:
    class RecordingPainter:
        def __init__(self) -> None:
            self.ellipses = 0
            self.lines = 0

        def drawEllipse(self, *_args) -> None:
            self.ellipses += 1

        def drawLine(self, _line) -> None:
            self.lines += 1

        def __getattr__(self, _name):
            return lambda *args, **kwargs: None

    depth = np.linspace(100.0, 200.0, 5_001)
    dataset = Dataset(
        "dense-pdf-ratio",
        "Dense PDF ratio",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    ratio = CurveData(
        CurveMetadata(
            "ratio",
            "C1_C2",
            "C1_C2",
            "ratio",
            None,
            dataset.dataset_id,
        ),
        2.0 + np.sin(depth * 0.3),
    )
    painter = RecordingPainter()
    rect = QRectF(0.0, 0.0, 100.0, 180.0)

    _draw_curves(
        painter,  # type: ignore[arg-type]
        rect,
        DepthPage(100.0, 200.0, 100, 100.0),
        dataset,
        (ratio,),
        {"ratio": (1.0, 3.0)},
        point_series=True,
    )

    assert painter.lines == 0
    assert GAS_SCATTER_VERTICAL_SPACING <= 1.5
    assert GAS_PRINT_POINT_RADIUS_PT <= 0.6
    assert int(rect.height() / 1.5) <= painter.ellipses <= gas_scatter_point_budget(
        rect.height()
    )


def test_dense_ratio_pdf_markers_do_not_overlap_into_worms() -> None:
    class RecordingPainter:
        def __init__(self) -> None:
            self.ellipse_rects: list[QRectF] = []
            self.lines = 0

        def drawEllipse(self, rect) -> None:
            self.ellipse_rects.append(QRectF(rect))

        def drawLine(self, _line) -> None:
            self.lines += 1

        def __getattr__(self, _name):
            return lambda *args, **kwargs: None

    depth = np.linspace(100.0, 200.0, 5_001)
    dataset = Dataset(
        "dense-pdf-ratio-overlap",
        "Dense PDF ratio overlap",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    ratio = CurveData(
        CurveMetadata(
            "ratio-overlap",
            "C1_C2",
            "C1_C2",
            "ratio",
            None,
            dataset.dataset_id,
        ),
        2.0 + np.sin(depth * 0.3),
    )
    rect = QRectF(0.0, 0.0, 100.0, 180.0)
    painter = RecordingPainter()

    _draw_curves(
        painter,  # type: ignore[arg-type]
        rect,
        DepthPage(100.0, 200.0, 100, 100.0),
        dataset,
        (ratio,),
        {"ratio-overlap": (1.0, 3.0)},
        point_series=True,
    )

    markers = painter.ellipse_rects
    assert painter.lines == 0
    assert 0 < len(markers) <= gas_scatter_point_budget(rect.height())
    assert all(
        abs(marker.width() - marker.height()) < 1e-9
        for marker in markers
    )

    ordered = sorted(markers, key=lambda marker: marker.center().y())
    longest_overlap_chain = 1
    current_overlap_chain = 1
    for previous, current in zip(ordered, ordered[1:], strict=False):
        vertical_overlap = (
            current.center().y() - previous.center().y()
            < (previous.height() + current.height()) / 2.0
        )
        same_column = abs(current.center().x() - previous.center().x()) < (
            previous.width() + current.width()
        ) / 2.0
        if vertical_overlap and same_column:
            current_overlap_chain += 1
            longest_overlap_chain = max(
                longest_overlap_chain,
                current_overlap_chain,
            )
        else:
            current_overlap_chain = 1

    # A small local overlap is acceptable for extrema from one depth bucket.
    # What must never return is a long same-column chain that reads as a line.
    assert longest_overlap_chain <= 3


def test_report_ratio_contract_uses_continuous_scaled_subtracks() -> None:
    whole = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_chart.py"
    ).read_text(encoding="utf-8")
    enhanced = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_pdf_chart_enhanced.py"
    ).read_text(encoding="utf-8")

    assert 'panel_name == "ratios" and _draw_ratio_preview_tracks(' in whole
    assert 'point_series = False' in whole
    assert 'gas_ratio_scale_ticks' in whole
    assert 'panel_name == "ratios" and _draw_ratio_tracks(' in enhanced
    assert 'point_series=False' in enhanced
    assert 'gas_ratio_scale_ticks' in enhanced

def test_constant_gas_curve_keeps_true_percentiles_and_a_visible_trace(qapp) -> None:
    depth = np.linspace(0.0, 10.0, 11)
    dataset = Dataset("constant-gas", "Constant gas", DatasetKind.GTI, DepthDomain.MD, depth)
    curve = CurveData(
        CurveMetadata("constant", "S1500", "TG", "%", None, dataset.dataset_id),
        np.zeros(depth.size),
    )
    dataset.curves["constant"] = curve
    page = DepthPage(0.0, 10.0, 100, 100.0)
    ranges = _curve_ranges((("total", (curve,)),), dataset, page=page)
    low, high = ranges["constant"]
    assert low < 0.0 < high
    assert high - low >= 2e-6

    image = QImage(100, 100, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    _draw_curves(painter, QRectF(0.0, 0.0, 100.0, 100.0), page, dataset, (curve,), ranges)
    painter.end()
    assert image.pixelColor(50, 50).name() != "#ffffff"


def test_whole_well_chart_uses_shared_fluid_markers_without_long_callouts() -> None:
    source = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_chart.py"
    ).read_text(encoding="utf-8")

    assert "hydrocarbon_fluid_markers" in source
    assert "_draw_whole_well_fluid_markers(" in source
    assert "_draw_whole_well_fluid_legend(" in source
    assert "fluid_marker_spec(candidate.fluid_hypothesis)" in source
    assert "marker_lane_offsets" in source
    assert "minimum_gap=badge_height + 2.0" in source
    assert "len(candidates) <= 24" not in source
    assert 'QColor("#f59e0b")' not in source


def test_print_html_isolates_chart_methodology_from_following_chart_page(qapp) -> None:
    session = _session_with_report_curves()
    dataset = session.current_dataset
    assert dataset is not None
    report = build_hydrocarbon_interpretation_report(session)

    html = hydrocarbon_interpretation_html_with_front_chart(
        report,
        dataset,
        AppLanguage.RU,
        print_layout=True,
    )

    assert "<div class='interpretation-chart-key'" in html
    assert "<section class='interpretation-chart-key'" not in html
    assert "page-break-before:always" in html
    assert "page-break-after:always" in html
    key_position = html.index("Пояснения к графикам")
    chart_position = html.index("Графики интерпретационных кривых по глубине")
    assert key_position < chart_position


def test_pdf_starts_chart_section_with_methodology_not_geology_catalog() -> None:
    source = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_pdf_renderer.py"
    ).read_text(encoding="utf-8")

    assert "paginate_geology_legend(" not in source
    assert "build_interpretation_geology_legend(" not in source
    assert "ReportLegendMode.COMPACT" in source
    assert "legend_reference_pages_emitted = True" in source
    assert "A separate geology-catalog page before it is not useful" in source
    method_render_index = source.index("render_report_html(")
    chart_render_index = source.index("render_chart_pages(", method_render_index)
    assert method_render_index < chart_render_index

@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("hide_legend", [False, True])
def test_overflowing_geology_legend_follows_charts_without_losing_symbols(qapp, tmp_path, language, hide_legend):
    from geoworkbench.domain.report_composition import ReportLegendMode
    from geoworkbench.printing.geology_track_rendering import FrozenCuttingsComponent, FrozenCuttingsSample
    from geoworkbench.printing.hydrocarbon_interpretation_geology import InterpretationGeologySnapshot
    from geoworkbench.project.lithotype_catalog_models import CatalogLithotype

    session = _session_with_report_curves(depth_span=30, samples=61)
    report = build_hydrocarbon_interpretation_report(session)
    count = 120
    geology = InterpretationGeologySnapshot(
        samples=(FrozenCuttingsSample("many-rocks", 1300, 1330,
            tuple(FrozenCuttingsComponent(str(index), 100 / count) for index in range(count))),),
        lithotypes=tuple(CatalogLithotype(str(index), f"R{index}", f"Rock {index}", f"Rock {index}",
            "sedimentary", "#c8c8b8", "carbonate", True, name_kk=f"Rock {index}") for index in range(count)),
    )
    target = export_hydrocarbon_interpretation_pdf(report, tmp_path / "overflow.pdf",
        dataset=session.current_dataset, include_chart=True, language=language, geology=geology,
        legend_mode=ReportLegendMode.HIDE if hide_legend else ReportLegendMode.FULL)
    titles = {
        AppLanguage.RU: ("Пояснения к графикам", "Графики интерпретационных кривых", "Геологическая легенда"),
        AppLanguage.KK: ("Графиктерге түсіндірме", "Тереңдік бойынша интерпретациялық қисықтар графиктері", "Геологиялық легенда"),
        AppLanguage.EN: ("Chart explanations", "Depth plots of interpretation curves", "Geology legend"),
    }
    with fitz.open(target) as document:
        texts = [page.get_text() for page in document]
    method, chart, legend = titles[language]
    method_index = next(index for index, text in enumerate(texts) if method in text)
    chart_indices = [index for index, text in enumerate(texts) if chart in text]
    assert chart_indices and method_index < min(chart_indices)
    if hide_legend:
        assert not any(legend in text for text in texts)
        assert not any("R119" in text for text in texts)
    else:
        legend_indices = [index for index, text in enumerate(texts) if legend in text and "R0" in text]
        assert legend_indices and min(legend_indices) > max(chart_indices)
        symbols = "".join("".join(text.split()) for text in texts[max(chart_indices) + 1:])
        for index in range(count):
            assert f"R{index}—Rock{index}" in symbols


def test_whole_well_report_chart_is_embedded_before_tables(qapp) -> None:
    session = _session_with_report_curves()
    dataset = session.current_dataset
    assert dataset is not None
    report = build_hydrocarbon_interpretation_report(session)

    uri = hydrocarbon_interpretation_chart_data_uri(report, dataset, AppLanguage.RU)
    html = hydrocarbon_interpretation_html_with_front_chart(
        report,
        dataset,
        AppLanguage.RU,
    )

    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > 10_000
    chart_position = html.index("Графики интерпретационных кривых по глубине")
    methods_position = html.index("Методы и доступность")
    assert chart_position < methods_position
    assert "data:image/png;base64," in html
    assert "max-width:1050px" in html
    assert "margin:0 auto" in html
    assert 'width="1050"' not in html


def test_whole_well_pdf_contains_chart_image(qapp, tmp_path) -> None:
    session = _session_with_report_curves()
    dataset = session.current_dataset
    assert dataset is not None
    report = build_hydrocarbon_interpretation_report(session)
    target = tmp_path / "mud-gas-with-curves.pdf"

    exported = export_hydrocarbon_interpretation_pdf(
        report,
        target,
        language=AppLanguage.RU,
        dataset=dataset,
        include_chart=True,
    )

    payload = target.read_bytes()
    assert exported == target
    assert payload.startswith(b"%PDF")
    assert target.stat().st_size > 20_000
    assert _pdf_page_count(payload) >= 3


def test_long_well_pdf_uses_more_chart_pages_than_short_well(qapp, tmp_path) -> None:
    short_session = _session_with_report_curves(depth_span=40.0, samples=161)
    long_session = _session_with_report_curves(depth_span=3_000.0, samples=1_501)
    short_dataset = short_session.current_dataset
    long_dataset = long_session.current_dataset
    assert short_dataset is not None
    assert long_dataset is not None
    short_target = tmp_path / "short-well.pdf"
    long_target = tmp_path / "long-well.pdf"

    export_hydrocarbon_interpretation_pdf(
        build_hydrocarbon_interpretation_report(short_session),
        short_target,
        language=AppLanguage.RU,
        dataset=short_dataset,
        include_chart=True,
    )
    export_hydrocarbon_interpretation_pdf(
        build_hydrocarbon_interpretation_report(long_session),
        long_target,
        language=AppLanguage.RU,
        dataset=long_dataset,
        include_chart=True,
    )

    short_pages = _pdf_page_count(short_target.read_bytes())
    long_pages = _pdf_page_count(long_target.read_bytes())
    assert short_pages >= 3
    assert long_pages > short_pages
    assert long_pages <= short_pages + 80


def test_workspace_exposes_primary_recalculation_and_chart_actions(qapp) -> None:
    workspace = InterpretationReportWorkspace(
        InterpretationCalculationController(ProjectSession()),
        language=AppLanguage.RU,
    )

    assert workspace.recalculate_all_button.text().startswith("3. Рассчитать кривые")
    assert workspace.refresh_chart_report_button.text() == "4. Обновить и проверить отчёт"
    report_index = workspace.report_mode.findData("well_text")
    assert report_index >= 0
    assert "с графиками" in workspace.report_mode.itemText(report_index)
    workspace.close()


def test_pdf_chart_breaks_clipped_outlier_spikes_and_limits_band_glare() -> None:
    base = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_pdf_chart.py"
    ).read_text(encoding="utf-8")
    enhanced = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_pdf_chart_enhanced.py"
    ).read_text(encoding="utf-8")

    assert "break_clipped_spike" in base
    assert "(clipped or previous_clipped)" in base
    assert "abs(normalized - previous_normalized) >= 0.72" in base
    assert "if previous is not None and not break_clipped_spike:" in base
    assert "continuous_depth_segments(" in base
    assert "limit=max(2, int(indices.size))" in base
    assert "band_color.setAlpha(12)" in enhanced


def test_report_curve_renderers_share_the_gap_segmenter() -> None:
    whole = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_chart.py"
    ).read_text(encoding="utf-8")
    pdf = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_pdf_chart.py"
    ).read_text(encoding="utf-8")

    assert "continuous_depth_segments(depth, depth_indices," in whole
    assert "continuous_depth_segments(" in pdf
    assert "limit=max(2, int(indices.size))" in pdf



def test_report_curve_legends_use_readable_parameter_names() -> None:
    depth = np.asarray([100.0, 101.0], dtype=np.float64)
    dataset = Dataset(
        "legend-labels",
        "Legend labels",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )

    rop = CurveData(
        CurveMetadata(
            "rop",
            "S106",
            "ROP",
            "м/ч",
            None,
            dataset.dataset_id,
        ),
        np.asarray([10.0, 11.0], dtype=np.float64),
    )
    flow_out = CurveData(
        CurveMetadata(
            "flow-out",
            "S1003",
            "FLOW_OUT",
            "л/c",
            None,
            dataset.dataset_id,
        ),
        np.asarray([60.0, 61.0], dtype=np.float64),
    )
    total_gas = CurveData(
        CurveMetadata(
            "tg",
            "TG_CALC",
            "TG_CALC",
            "%abs",
            None,
            dataset.dataset_id,
        ),
        np.asarray([0.1, 0.2], dtype=np.float64),
    )

    assert curve_display_name(rop, AppLanguage.RU) == "Скорость бур."
    assert curve_display_name(flow_out, AppLanguage.RU) == "Расх. на вых."
    assert curve_display_name(total_gas, AppLanguage.RU) == "Общий газ"

    legend = curve_legend_text(
        rop,
        10.0,
        11.0,
        AppLanguage.RU,
    )
    assert legend.startswith("Скорость бур. [м/ч]")
    assert "S106" not in legend


def test_report_method_hint_relabels_source_only_dexp_curve() -> None:
    report = SimpleNamespace(
        methods=(
            SimpleNamespace(
                curve_mnemonics=("DEXP",),
                available_mnemonics=("S224",),
            ),
        ),
    )
    hints = report_curve_label_hints(report)  # type: ignore[arg-type]
    curve = CurveData(
        CurveMetadata(
            "dexp-source",
            "S224",
            "S224",
            "",
            None,
            "dataset",
        ),
        np.asarray([1.0, 1.1], dtype=np.float64),
    )

    assert hints == {"S224": "DEXP"}
    assert (
        curve_display_name(
            curve,
            AppLanguage.RU,
            canonical_hint=hints["S224"],
        )
        == "D-exponent"
    )



def test_opus_chart_curve_labels_hide_internal_mnemonics() -> None:
    curve = CurveData(
        CurveMetadata(
            "opus-total",
            "OPUS_TG_PCT",
            "OPUS_TG_PCT",
            "%об.",
            None,
            "dataset",
        ),
        np.asarray([0.1, 0.2], dtype=np.float64),
    )

    assert curve_display_name(curve, AppLanguage.RU) == "Общий газ ОПУС"
    assert curve_display_name(curve, AppLanguage.KK) == "ОПУС жалпы газы"
    assert curve_display_name(curve, AppLanguage.EN) == "OPUS total gas"
