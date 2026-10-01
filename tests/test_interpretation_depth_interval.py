from __future__ import annotations

from dataclasses import replace
import zipfile

import fitz
import numpy as np
from openpyxl import load_workbook
import pytest

from geoworkbench.domain.depth_interval import DepthInterval, DepthIntervalError, scope_dataset
from geoworkbench.domain.models import (
    CuttingsSample,
    Dataset,
    DatasetKind,
    DepthDomain,
    InterpretationInterval,
    WellInterpretation,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.project.interpretation_depth_scope import scope_interpretation_session
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.hydrocarbon_interpretation import (
    build_hydrocarbon_interpretation_report,
    build_opus_interpretation_report,
    hydrocarbon_interpretation_html,
    set_normalized_gas_report_mode,
)


def _session() -> ProjectSession:
    dataset = Dataset(
        "interval", "Depth selection", DatasetKind.GTI, DepthDomain.MD, np.arange(1000.0, 1100.0)
    )
    for name, value, unit in (
        ("C1", 8.0, "%"),
        ("C2", 1.0, "%"),
        ("C3", 0.5, "%"),
        ("IC4", 0.1, "%"),
        ("NC4", 0.2, "%"),
        ("IC5", 0.1, "%"),
        ("NC5", 0.1, "%"),
        ("ROP", 18.288, "m/h"),
        ("RPM", 100.0, "rpm"),
        ("WOB", 22.6796, "t"),
        ("BIT", 254.0, "mm"),
        ("FLOW", 1892.7, "L/min"),
        ("MW", 1.44, "g/cm3"),
    ):
        dataset.upsert_curve(name, np.full(100, value), unit=unit, provenance="source")
    gas = np.full(100, 1000.0)
    gas[30:61] = 5.0
    gas[45:48] = 50.0
    dataset.upsert_curve("TG", gas, unit="%", provenance="source")
    dataset.upsert_curve("OPUS_TG_PCT", gas.copy(), unit="%", provenance="source")
    session = ProjectSession()
    session.add_dataset(dataset, "Interval well")
    well = session.current_well
    assert well is not None
    well.cuttings = [
        CuttingsSample("outside", 1000.0, 1010.0, lba_group=5),
        CuttingsSample("inside", 1020.0, 1040.0, lba_group=2),
    ]
    well.interpretations["manual"] = WellInterpretation(
        "manual",
        "Manual",
        intervals=[
            InterpretationInterval("outside", 1000.0, 1010.0, "gas", "outside-only"),
            InterpretationInterval("crossing", 1020.0, 1070.0, "gas", "crossing-selected"),
        ],
    )
    session.dirty = False
    return session


@pytest.mark.parametrize(
    "method", ["calculate_standard_curves", "calculate_normalized_gas", "calculate_opus_curves"]
)
def test_selected_calculations_preserve_source_and_unselected_rows(method):
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    source = {key: item.values.copy() for key, item in dataset.curves.items()}
    controller = InterpretationCalculationController(
        session, depth_interval=DepthInterval(1030.2, 1060.8)
    )
    result = getattr(controller, method)()
    assert result.changed
    mask = controller.depth_interval.row_mask(dataset)
    for name in result.changed:
        curve = dataset.curve_by_mnemonic(name)
        assert curve is not None
        assert np.isnan(curve.values[~mask]).all()
    for key, values in source.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)
    # Recalculation in another interval retains existing calculated values elsewhere.
    before = {key: item.values.copy() for key, item in dataset.curves.items()}
    controller.depth_interval = DepthInterval(1070.0, 1090.0)
    second_mask = controller.depth_interval.row_mask(dataset)
    getattr(controller, method)()
    for key, values in before.items():
        np.testing.assert_array_equal(
            dataset.curves[key].values[~second_mask], values[~second_mask]
        )


@pytest.mark.parametrize(
    "builder", [build_hydrocarbon_interpretation_report, build_opus_interpretation_report]
)
def test_selected_report_recalculates_background_and_clips_context(builder):
    session = _session()
    interval = DepthInterval(1030.2, 1060.8)
    if builder is build_opus_interpretation_report:
        InterpretationCalculationController(session).calculate_opus_curves()
        session.dirty = False
    selected = scope_interpretation_session(session, interval)
    expected = builder(selected)
    actual = builder(session, depth_interval=interval)
    assert actual.baseline_median == expected.baseline_median
    assert actual.robust_scale == expected.robust_scale
    assert actual.candidates == expected.candidates
    assert actual.opus_gasomer == expected.opus_gasomer
    assert actual.baseline_median != builder(session).baseline_median
    assert actual.analysis_depth_interval == interval
    assert [(item.top_depth, item.bottom_depth) for item in actual.manual_intervals] == [
        (1030.2, 1060.8)
    ]
    assert [
        (item.sample_id, item.top_depth, item.bottom_depth)
        for item in selected.current_well.cuttings
    ] == [("inside", 1030.2, 1040.0)]
    assert session.current_well.cuttings[1].top_depth == 1020.0
    assert not session.dirty
    assert "1030.20–1060.80" in hydrocarbon_interpretation_html(actual)


def test_selected_report_retains_selected_normalized_gas_mode():
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    dataset.upsert_curve("TG_NORM", np.full(100, 11.0), unit="unit", provenance="source")
    dataset.upsert_curve(
        "TG_NORM_CALC", np.full(100, 22.0), unit="unit", provenance="calculation:test"
    )
    set_normalized_gas_report_mode(session, "local")
    report = build_hydrocarbon_interpretation_report(
        session, depth_interval=DepthInterval(1030.0, 1060.0)
    )
    assert report.primary_mnemonic == "TG_NORM_CALC"


@pytest.mark.parametrize(
    "bounds",
    [
        (1060.0, 1030.0),
        (900.0, 1050.0),
        (1030.0, 1200.0),
        (1030.2, 1030.8),
        (1030.0, 1030.0),
        (float("nan"), 1050.0),
    ],
)
def test_invalid_or_empty_interval_fails_before_mutation(bounds):
    session = _session()
    with pytest.raises(DepthIntervalError):
        controller = InterpretationCalculationController(
            session, depth_interval=DepthInterval(*bounds)
        )
        controller.calculate_standard_curves()
    assert not session.dirty
    assert session.current_dataset.curve_by_mnemonic("WH") is None


def test_time_axis_cannot_be_used_as_depth_interval():
    dataset = Dataset("time", "Time", DatasetKind.GTI, DepthDomain.TIME, np.arange(100.0))
    with pytest.raises(DepthIntervalError, match="MD/TVD/TVDSS"):
        scope_dataset(dataset, DepthInterval(10.0, 50.0))


def test_selected_chart_uses_only_selected_curve_values_and_geology(qapp, monkeypatch):
    from geoworkbench.printing import hydrocarbon_interpretation_chart as chart
    from geoworkbench.printing.hydrocarbon_interpretation_geology import (
        interpretation_geology_snapshot,
    )

    session = _session()
    interval = DepthInterval(1030.2, 1060.8)
    report = build_hydrocarbon_interpretation_report(session, depth_interval=interval)
    seen = []
    original = chart._draw_panel

    def capture(painter, rect, depth, finite, top, bottom, name, curves, *args):
        seen.append(
            (
                depth.copy(),
                top,
                bottom,
                {curve.metadata.original_mnemonic: curve.values.copy() for curve in curves},
            )
        )
        return original(painter, rect, depth, finite, top, bottom, name, curves, *args)

    monkeypatch.setattr(chart, "_draw_panel", capture)
    selected = scope_interpretation_session(session, interval)
    geology = interpretation_geology_snapshot(selected)
    assert geology is not None
    assert [sample.sample_id for sample in geology.samples] == ["inside"]
    assert chart.hydrocarbon_interpretation_chart_data_uri(
        report, session.current_dataset, geology=geology
    )
    assert seen
    for depths, top, bottom, curves in seen:
        np.testing.assert_array_equal(depths, np.arange(1031.0, 1061.0))
        assert (top, bottom) == (1030.2, 1060.8)
        for values in curves.values():
            assert values.size == 30
    assert max(seen[0][3]["TG"]) == 50.0


def test_selected_gas_context_is_clipped_before_measurement_audit():
    from geoworkbench.domain.gas_context_events import GasContextEvent, GasContextEventType

    session = _session()
    session.current_well.gas_context_events = [
        GasContextEvent(
            "outside",
            GasContextEventType.OTHER_TECHNOLOGICAL,
            1000.0,
            1010.0,
            depth_domain=DepthDomain.MD,
        ),
        GasContextEvent(
            "crossing",
            GasContextEventType.OTHER_TECHNOLOGICAL,
            1020.0,
            1040.0,
            depth_domain=DepthDomain.MD,
        ),
    ]
    report = build_hydrocarbon_interpretation_report(
        session, depth_interval=DepthInterval(1030.2, 1060.8)
    )
    assert [
        (event.event_id, event.top_depth, event.bottom_depth) for event in report.gas_context_events
    ] == [("crossing", 1030.2, 1040.0)]
    assert [item.event_id for item in report.gas_context_audit] == ["crossing"]


def test_negative_unsorted_depths_and_other_indexes_keep_row_alignment():
    dataset = Dataset(
        "negative",
        "Negative",
        DatasetKind.GTI,
        DepthDomain.TVDSS,
        np.array([-10.0, -50.0, -30.0, -20.0, np.nan]),
    )
    dataset.upsert_curve("C1", np.array([1.0, 5.0, 3.0, 2.0, 0.0]), unit="%", provenance="source")
    selected = scope_dataset(dataset, DepthInterval(-35.0, -15.0))
    np.testing.assert_array_equal(selected.depth, [-30.0, -20.0])
    np.testing.assert_array_equal(selected.active_index.values, [-30.0, -20.0])
    np.testing.assert_array_equal(selected.curve_by_mnemonic("C1").values, [3.0, 2.0])


def test_all_exports_use_calculated_interval(tmp_path, qapp):
    from geoworkbench.data.hydrocarbon_interpretation_export_readable import (
        export_readable_hydrocarbon_interpretation_xlsx,
    )
    from geoworkbench.data.hydrocarbon_interpretation_export_docx_polished import (
        export_polished_hydrocarbon_interpretation_docx,
    )
    from geoworkbench.printing.hydrocarbon_interpretation_report import (
        export_hydrocarbon_interpretation_pdf,
    )
    from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
        default_interpretation_report_identity,
    )
    from geoworkbench.services.localization import AppLanguage

    session = _session()
    dataset = session.current_dataset
    interval = DepthInterval(1030.2, 1060.8)
    InterpretationCalculationController(session).calculate_opus_curves()
    report = build_opus_interpretation_report(session, depth_interval=interval)
    identity = replace(
        default_interpretation_report_identity(report, AppLanguage.RU), interval="1000–1099 m"
    )
    xlsx = export_readable_hydrocarbon_interpretation_xlsx(
        report, dataset, tmp_path / "selected.xlsx"
    )
    workbook = load_workbook(xlsx)
    try:
        audit = next(sheet for sheet in workbook if sheet.sheet_state == "hidden")
        depths = [row[0] for row in list(audit.values)[1:]]
        assert depths == list(np.arange(1031.0, 1061.0))
        assert "1030.20–1060.80" in str(list(workbook.worksheets[0].values))
    finally:
        workbook.close()
    docx = export_polished_hydrocarbon_interpretation_docx(
        report, tmp_path / "selected.docx", dataset=dataset, identity=identity
    )
    with zipfile.ZipFile(docx) as package:
        xml = package.read("word/document.xml").decode()
        assert "1030.20–1060.80" in xml
        assert "outside-only" not in xml
    pdf = export_hydrocarbon_interpretation_pdf(
        report, tmp_path / "selected.pdf", dataset=dataset, identity=identity, include_chart=True
    )
    with fitz.open(pdf) as document:
        text = "".join(page.get_text() for page in document)
        assert "1030.20" in text and "1060.80" in text
        assert "outside-only" not in text


def test_workspace_applies_interval_and_resets_for_new_well(qapp):
    from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace

    session = _session()
    controller = InterpretationCalculationController(session)
    workspace = InterpretationReportWorkspace(controller)
    workspace.resize(1050, 820)
    workspace.show()
    qapp.processEvents()
    assert workspace.configuration_shell.isAncestorOf(workspace.depth_interval_panel)
    assert workspace.depth_interval_mode.isVisible()
    workspace.depth_interval_mode.setCurrentIndex(1)
    workspace.depth_interval_top.setValue(1030.2)
    workspace.depth_interval_bottom.setValue(1060.8)
    workspace.depth_interval_apply.click()
    assert controller.depth_interval == DepthInterval(1030.2, 1060.8)
    assert workspace.report.analysis_depth_interval == controller.depth_interval
    workspace.depth_interval_bottom.setValue(1020.0)
    workspace.depth_interval_apply.click()
    assert workspace.report.analysis_depth_interval == DepthInterval(1030.2, 1060.8)
    session.add_dataset(
        Dataset("second", "Second", DatasetKind.GTI, DepthDomain.MD, np.arange(2000.0, 2100.0)),
        "Second well",
    )
    workspace.refresh()
    assert controller.depth_interval is None
    assert workspace.report.analysis_depth_interval is None
    assert workspace.depth_interval_top.value() == 2000.0
    workspace.close()


@pytest.mark.parametrize("front_chart", [False, True])
def test_selected_html_variants_scope_statistics(front_chart, qapp, monkeypatch):
    from geoworkbench.printing.hydrocarbon_interpretation_chart import (
        hydrocarbon_interpretation_html_with_chart,
    )
    from geoworkbench.printing.hydrocarbon_interpretation_chart_front import (
        hydrocarbon_interpretation_html_with_front_chart,
    )

    session = _session()
    interval = DepthInterval(1030.2, 1060.8)
    report = build_hydrocarbon_interpretation_report(session, depth_interval=interval)
    seen = []

    def capture(html, _report, dataset, _language):
        seen.append(dataset.depth.copy())
        return html

    monkeypatch.setattr(
        "geoworkbench.services.hydrocarbon_interpretation_gas_html.inject_interval_gas_statistics_html",
        capture,
    )
    render = (
        hydrocarbon_interpretation_html_with_front_chart
        if front_chart
        else hydrocarbon_interpretation_html_with_chart
    )
    html = render(report, session.current_dataset)
    assert "1030.20–1060.80" in html
    assert len(seen) == 1
    np.testing.assert_array_equal(seen[0], np.arange(1031.0, 1061.0))
