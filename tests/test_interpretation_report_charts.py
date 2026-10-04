from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
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
from geoworkbench.printing.hydrocarbon_interpretation_pdf_chart import (
    _curve_ranges,
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
from geoworkbench.services.hydrocarbon_interpretation import (
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


def test_pdf_curve_renderer_uses_lines_for_ratios_and_points_for_opus() -> None:
    class RecordingPainter:
        def __init__(self) -> None:
            self.lines = 0
            self.ellipses = 0

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

        def drawEllipse(self, _rect) -> None:
            self.ellipses += 1

    depth = np.linspace(100.0, 104.0, 5)
    dataset = Dataset(
        "ratio-line-report",
        "Ratio line report",
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
    opus = CurveData(
        CurveMetadata(
            "opus",
            "OPUS3",
            "OPUS3",
            "ratio",
            None,
            dataset.dataset_id,
        ),
        np.linspace(1.0, 2.0, 5),
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
        point_series=False,
    )
    assert ratio_painter.lines > 0
    assert ratio_painter.ellipses == 0

    opus_painter = RecordingPainter()
    _draw_curves(
        opus_painter,  # type: ignore[arg-type]
        rect,
        page,
        dataset,
        (opus,),
        {"opus": (1.0, 2.0)},
        point_series=True,
    )
    assert opus_painter.lines == 0
    assert opus_painter.ellipses > 0

def test_singleton_ratio_observation_survives_preview_and_pdf_range() -> None:
    class RecordingPainter:
        def __init__(self) -> None:
            self.ellipses = 0

        def drawEllipse(self, _rect) -> None:
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
    # A line cannot represent a singleton. The renderer keeps exactly the
    # factual observation as a compact fallback marker.
    assert preview.ellipses >= 1

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
        point_series=False,
    )
    assert pdf_painter.ellipses == 1

def test_report_panel_selector_keeps_singleton_opus_point_series() -> None:
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


def test_sparse_ratio_singleton_remains_visible_in_whole_well_preview() -> None:
    class RecordingPainter:
        def __init__(self) -> None:
            self.ellipses = 0

        def drawEllipse(self, _rect) -> None:
            self.ellipses += 1

        def __getattr__(self, _name):
            return lambda *args, **kwargs: None

    depth = np.arange(3_601, dtype=np.float64)
    values = np.full(depth.shape, np.nan, dtype=np.float64)
    values[1_235] = 2.5
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

    painter = RecordingPainter()
    _draw_panel(
        painter,  # type: ignore[arg-type]
        QRectF(0.0, 0.0, 120.0, 180.0),
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

    assert painter.ellipses >= 1

def test_dense_ratio_preview_uses_continuous_line_not_scatter() -> None:
    class RecordingPainter:
        def __init__(self) -> None:
            self.ellipses = 0
            self.lines = 0

        def drawEllipse(self, _rect) -> None:
            self.ellipses += 1

        def drawLine(self, _line) -> None:
            self.lines += 1

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
        2.0 + np.sin(depth / 17.0),
    )

    painter = RecordingPainter()
    _draw_panel(
        painter,  # type: ignore[arg-type]
        QRectF(0.0, 0.0, 120.0, 180.0),
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

    assert painter.lines > 0
    assert painter.ellipses == 0

def test_dense_ratio_pdf_uses_line_geometry_without_scatter_markers() -> None:
    class RecordingPainter:
        def __init__(self) -> None:
            self.ellipses = 0
            self.lines = 0

        def drawEllipse(self, _rect) -> None:
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

    _draw_curves(
        painter,  # type: ignore[arg-type]
        QRectF(0.0, 0.0, 100.0, 180.0),
        DepthPage(100.0, 200.0, 100, 100.0),
        dataset,
        (ratio,),
        {"ratio": (1.0, 3.0)},
        point_series=False,
    )

    assert painter.lines > 0
    assert painter.ellipses == 0

def test_report_panel_point_contract_is_opus_only() -> None:
    whole = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_chart.py"
    ).read_text(encoding="utf-8")
    pdf = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_pdf_chart.py"
    ).read_text(encoding="utf-8")
    enhanced = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_pdf_chart_enhanced.py"
    ).read_text(encoding="utf-8")

    for source in (whole, pdf, enhanced):
        assert 'panel_name == "opus"' in source
        assert 'point_series = panel_name in {"ratios", "opus"}' not in source
        assert 'point_series=panel_name in {"ratios", "opus"}' not in source

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
