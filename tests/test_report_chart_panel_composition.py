from __future__ import annotations

from dataclasses import replace
import json

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from geoworkbench.domain.report_composition import (
    DEFAULT_REPORT_CHART_PANELS,
    InterpretationReportComposition,
    ReportChartPanel,
    ReportChartPanelSettings,
)
from geoworkbench.printing import hydrocarbon_interpretation_chart as preview
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as printed
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    export_hydrocarbon_interpretation_pdf_with_passport,
)
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.hydrocarbon_interpretation import build_hydrocarbon_interpretation_report
from geoworkbench.services.localization import AppLanguage
from geoworkbench.storage.project_codec import ProjectFormatError, load_project_document
from geoworkbench.ui.interpretation_print_layout_dialog import InterpretationPrintLayoutDialog
from test_interpretation_report_charts import _session_with_report_curves


def _settings() -> ReportChartPanelSettings:
    return ReportChartPanelSettings(
        order=(ReportChartPanel.DRILLING, ReportChartPanel.RATIOS,
               ReportChartPanel.TOTAL, ReportChartPanel.OPUS),
        hidden=(ReportChartPanel.RATIOS,),
    )


def _session() -> ProjectSession:
    session = _session_with_report_curves(depth_span=30, samples=61)
    dataset = session.current_dataset
    assert dataset is not None
    session.report_compositions[dataset.dataset_id] = InterpretationReportComposition(
        composition_id="rpt-columns", chart_panels=_settings(),
    )
    return session


@pytest.mark.parametrize("suffix", [".geolog.json", ".geologpkg"])
def test_column_choices_survive_project_controller_save_reopen(tmp_path, suffix: str) -> None:
    session = _session()
    controller = ProjectController(session=session)
    target = tmp_path / f"columns{suffix}"
    controller.save_project(target)
    restored = ProjectController().open_project(target)
    assert restored.report_compositions == session.report_compositions
    assert not restored.dirty


def test_old_v37_without_panel_settings_keeps_existing_defaults(tmp_path) -> None:
    session = _session()
    target = tmp_path / "legacy.geolog.json"
    ProjectController(session=session).save_project(target)
    data = json.loads(target.read_text())
    dataset_id = session.current_dataset.dataset_id
    data["report_compositions"][dataset_id].pop("chart_panels")
    target.write_text(json.dumps(data), encoding="utf-8")
    loaded = load_project_document(target)
    assert loaded.report_compositions[dataset_id].chart_panels == DEFAULT_REPORT_CHART_PANELS


@pytest.mark.parametrize("invalid", [
    None, [], {"order": ["total"], "hidden": []},
    {"order": ["total", "ratios", "drilling", "opus"], "hidden": ["unknown"]},
    {"order": ["total", "ratios", "drilling", "opus"], "hidden": ["total", "total"]},
    {"order": ["total", "total", "drilling", "opus"], "hidden": []},
    {"order": ["total", "ratios", "drilling", "opus"], "hidden": False},
    {"order": ["total", "ratios", "drilling", "opus"], "hidden": [], "extra": 1},
])
def test_load_rejects_malformed_or_unpermitted_panel_settings(tmp_path, invalid: object) -> None:
    session = _session()
    target = tmp_path / "invalid.geolog.json"
    ProjectController(session=session).save_project(target)
    data = json.loads(target.read_text())
    data["report_compositions"][session.current_dataset.dataset_id]["chart_panels"] = invalid
    target.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProjectFormatError, match="report composition"):
        load_project_document(target)


@pytest.mark.parametrize("language", list(AppLanguage))
def test_dialog_restores_reorders_and_preserves_hidden_positions(qapp, language) -> None:
    initial = InterpretationReportComposition(composition_id="columns", chart_panels=_settings())
    dialog = InterpretationPrintLayoutDialog(language=language, initial=initial)
    assert dialog.selected_composition() == initial
    dialog.chart_panel_list.setCurrentRow(0)
    dialog._move_chart_panel(-1)
    assert dialog.selected_composition() == initial
    dialog.findChild(QPushButton, "chart-panel-down").click()
    selected = dialog.selected_composition()
    assert selected.chart_panels.order[:2] == (ReportChartPanel.RATIOS, ReportChartPanel.DRILLING)
    assert selected.chart_panels.hidden == (ReportChartPanel.RATIOS,)
    item = dialog.chart_panel_list.item(0)
    item.setCheckState(Qt.CheckState.Checked)
    assert dialog.selected_composition().chart_panels.hidden == ()
    dialog.reject()
    assert initial.chart_panels == _settings()
    dialog.close()


@pytest.mark.parametrize("profile,expected", [
    ("standard", ["total", "ratios", "drilling"]),
    ("opus", ["total", "opus", "ratios"]),
])
def test_default_order_preserves_both_report_profiles(profile, expected) -> None:
    session = _session()
    dataset = session.current_dataset
    report = build_hydrocarbon_interpretation_report(session)
    report = replace(report, report_profile=profile)
    # Empty panels still identify the allowed profile; renderers omit missing data.
    assert [name for name, _ in preview._panel_curves(report, dataset)] == expected
    assert [name for name, _ in printed.base_chart._panel_curves(report, dataset)] == expected


@pytest.mark.parametrize("language", list(AppLanguage))
def test_actual_preview_and_pdf_use_same_visible_order_without_mutating_data(
    qapp, tmp_path, monkeypatch, language,
) -> None:
    session = _session()
    dataset = session.current_dataset
    original = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    report = build_hydrocarbon_interpretation_report(session)
    seen_preview = []
    seen_pdf = []
    draw_preview = preview._draw_panel
    draw_pdf = printed._draw_chart_page

    def capture_preview(*args, **kwargs):
        seen_preview.append((args[6], args[1].left()))
        return draw_preview(*args, **kwargs)

    def capture_pdf(*args, **kwargs):
        seen_pdf.append([name for name, curves in args[7]])
        return draw_pdf(*args, **kwargs)

    monkeypatch.setattr(preview, "_draw_panel", capture_preview)
    monkeypatch.setattr(printed, "_draw_chart_page", capture_pdf)
    uri = preview.hydrocarbon_interpretation_chart_data_uri(
        report, dataset, language, chart_panels=_settings(),
    )
    result = export_hydrocarbon_interpretation_pdf_with_passport(
        session, report, tmp_path / "columns.pdf", include_chart=True,
        language=language, chart_panels=_settings(),
    )
    assert uri.startswith("data:image/png;base64,")
    assert [name for name, _ in seen_preview] == ["drilling", "total"]
    assert seen_preview[0][1] < seen_preview[1][1]
    assert seen_pdf and all(names == ["drilling", "total"] for names in seen_pdf)
    assert result.primary_path.stat().st_size > 0
    options = dict(result.passport.render.options)
    assert options["chart_panel_order"] == "drilling,ratios,total,opus"
    assert options["hidden_chart_panels"] == "ratios"
    baseline = export_hydrocarbon_interpretation_pdf_with_passport(
        session, report, tmp_path / "baseline.pdf", language=language,
    )
    assert result.passport.dataset_sha256 == baseline.passport.dataset_sha256
    for key, values in original.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)


def test_all_hidden_produces_no_chart_and_keeps_saved_order(qapp, tmp_path, monkeypatch) -> None:
    session = _session()
    dataset = session.current_dataset
    report = build_hydrocarbon_interpretation_report(session)
    settings = ReportChartPanelSettings(_settings().order, tuple(ReportChartPanel))
    assert preview.hydrocarbon_interpretation_chart_data_uri(
        report, dataset, chart_panels=settings,
    ) == ""
    def unexpected_chart(*args, **kwargs):
        pytest.fail("All-hidden composition must not render chart pages")
    from geoworkbench.printing import hydrocarbon_interpretation_pdf_renderer
    monkeypatch.setattr(hydrocarbon_interpretation_pdf_renderer, "render_chart_pages", unexpected_chart)
    result = export_hydrocarbon_interpretation_pdf_with_passport(
        session, report, tmp_path / "hidden.pdf", include_chart=True, chart_panels=settings,
    )
    assert result.primary_path.exists()
    assert settings.order == _settings().order


@pytest.mark.parametrize("language", list(AppLanguage))
def test_chart_explanations_follow_visible_columns_in_html_and_pdf(qapp, tmp_path, monkeypatch, language) -> None:
    from geoworkbench.printing import hydrocarbon_interpretation_chart_front as front
    from geoworkbench.printing import hydrocarbon_interpretation_pdf_renderer as renderer
    from geoworkbench.printing.hydrocarbon_interpretation_curve_labels import curve_display_name
    from geoworkbench.printing.interpretation_chart_key import interpretation_chart_key_html

    session = _session()
    dataset = session.current_dataset
    report = build_hydrocarbon_interpretation_report(session)
    titles = {
        curve.metadata.original_mnemonic: curve_display_name(curve, language)
        for curve in dataset.curves.values()
    }
    ordered = ReportChartPanelSettings(_settings().order)
    key = interpretation_chart_key_html(report, dataset, language, chart_panels=ordered)
    assert key.index(titles["DEXP"]) < key.index(titles["WH"])
    hidden_key = interpretation_chart_key_html(report, dataset, language, chart_panels=_settings())
    assert titles["DEXP"] in hidden_key
    assert titles["WH"] not in hidden_key
    all_hidden = ReportChartPanelSettings(ordered.order, tuple(ReportChartPanel))
    assert interpretation_chart_key_html(report, dataset, language, chart_panels=all_hidden) == ""
    seen = []

    def capture_key(*args, **kwargs):
        html = interpretation_chart_key_html(*args, **kwargs)
        seen.append((kwargs.get("chart_panels"), html))
        return html

    monkeypatch.setattr(front, "interpretation_chart_key_html", capture_key)
    monkeypatch.setattr(renderer, "interpretation_chart_key_html", capture_key)
    html = front.hydrocarbon_interpretation_html_with_front_chart(
        report, dataset, language, chart_panels=_settings(),
    )
    export_hydrocarbon_interpretation_pdf_with_passport(
        session, report, tmp_path / "key.pdf", language=language,
        include_chart=True, chart_panels=_settings(),
    )
    assert hidden_key in html
    assert seen == [(_settings(), hidden_key), (_settings(), hidden_key)]


def test_hidden_column_annotations_do_not_move_to_a_visible_neighbour(qapp, tmp_path, monkeypatch) -> None:
    from geoworkbench.domain.report_annotations import (
        ReportAnnotationAnchor, ReportAnnotationKind, ReportAnnotationRecord,
        report_annotation_scope_id,
    )
    from geoworkbench.printing.report_annotation_rendering import paint_report_annotations

    session = _session()
    dataset = session.current_dataset
    report = build_hydrocarbon_interpretation_report(session)
    annotation = ReportAnnotationRecord(
        annotation_id="hidden-column-note",
        scope_id=report_annotation_scope_id(
            session.current_well.well_id, dataset.dataset_id, "rpt-columns",
        ),
        kind=ReportAnnotationKind.TEXT,
        anchor=ReportAnnotationAnchor.DEPTH,
        track_key="curve:WH",
        depth=float(dataset.depth[len(dataset.depth) // 2]),
        text="Hidden ratio note",
    )
    observed = []

    def capture(*args, **kwargs):
        count = paint_report_annotations(*args, **kwargs)
        observed.append((count, kwargs["track_map"]))
        return count

    monkeypatch.setattr(preview, "paint_report_annotations", capture)
    monkeypatch.setattr(printed, "paint_report_annotations", capture)
    preview.hydrocarbon_interpretation_chart_data_uri(
        report, dataset, chart_panels=_settings(), annotations=(annotation,),
    )
    export_hydrocarbon_interpretation_pdf_with_passport(
        session, report, tmp_path / "annotation.pdf", include_chart=True,
        chart_panels=_settings(), annotations=(annotation,),
    )
    assert len(observed) >= 2
    assert all(count == 0 and "curve:wh" not in mapping for count, mapping in observed)
    assert all("curve:dexp" in mapping for _count, mapping in observed)
