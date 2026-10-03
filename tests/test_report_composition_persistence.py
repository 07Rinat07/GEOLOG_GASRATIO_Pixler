from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtGui import QPageLayout

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.printing import hydrocarbon_interpretation_chart as interpretation_chart
from geoworkbench.printing import hydrocarbon_interpretation_chart_front as chart_front
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as pdf_chart
from geoworkbench.printing import hydrocarbon_interpretation_pdf_renderer as pdf_renderer
from geoworkbench.printing.hydrocarbon_interpretation_geology_legend import (
    GeologyLegendItem,
    InterpretationGeologyLegend,
    geology_legend_height,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    GeologyTrackVisibility,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    InterpretationReportIdentity,
    identity_with_report_header_fields,
    report_header_fields_from_identity,
)
from geoworkbench.domain.report_composition import (
    InterpretationReportComposition,
    ReportHeaderFields,
    ReportLegendMode,
    ReportPageOrientation,
    ReportPrintOrder,
    ReportTrackVisibility,
    ensure_report_composition_id,
    report_header_fields,
    stable_report_composition_id,
    with_report_header_fields,
)
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.dataset_merge_controller import DatasetMergeController
from geoworkbench.project.depth_axis_controller import DepthAxisController
from geoworkbench.project.derived_dataset_controller import DerivedDatasetController
from geoworkbench.project.lag_correction_controller import LagCorrectionProjectController
from geoworkbench.project.time_to_depth_controller import TimeToDepthController
from geoworkbench.project.time_depth_aggregation_controller import TimeDepthAggregationController
from geoworkbench.ui import interpretation_report_workspace_final
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.storage.project_codec import (
    PROJECT_FORMAT_VERSION,
    ProjectDocument,
    load_project_document,
)
from geoworkbench.ui.interpretation_print_layout_dialog import (
    InterpretationPrintLayoutDialog,
    InterpretationPrintOrder,
)


def _project() -> Project:
    dataset = Dataset(
        "dataset-report-composition",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray([1000.0, 1001.0], dtype=np.float64),
    )
    well = Well("well-report-composition", "Well", datasets={dataset.dataset_id: dataset})
    return Project("project-report-composition", "Project", wells={well.well_id: well})


def _composition() -> InterpretationReportComposition:
    return InterpretationReportComposition(
        composition_id=stable_report_composition_id("dataset-report-composition"),
        orientation=ReportPageOrientation.LANDSCAPE,
        print_order=ReportPrintOrder.LAST_TO_FIRST,
        cuttings=ReportTrackVisibility.SHOW,
        lba=ReportTrackVisibility.HIDE,
        legend_mode=ReportLegendMode.COMPACT,
        header_ru=ReportHeaderFields(
            report_title="Русский заголовок",
            project_name="Проект",
            well_name="Скважина",
            revision="01",
        ),
        header_en=ReportHeaderFields(
            report_title="English title",
            project_name="Project",
            well_name="Well",
            revision="02",
        ),
    )


def test_project_v37_json_round_trip_preserves_report_composition(tmp_path) -> None:
    project = _project()
    target = tmp_path / "project.geolog.json"

    save_project(
        project,
        target,
        report_compositions={"dataset-report-composition": _composition()},
    )
    loaded = load_project_document(target)

    assert PROJECT_FORMAT_VERSION == 37
    assert loaded.report_compositions == {
        "dataset-report-composition": _composition()
    }


def test_legacy_v37_without_composition_id_gets_stable_dataset_identity(tmp_path) -> None:
    project = _project()
    target = tmp_path / "legacy-v37-composition-id.geolog.json"
    save_project(
        project,
        target,
        report_compositions={"dataset-report-composition": _composition()},
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["report_compositions"]["dataset-report-composition"].pop("composition_id")
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    first = load_project_document(target)
    second = load_project_document(target)
    expected = stable_report_composition_id("dataset-report-composition")

    assert first.report_compositions["dataset-report-composition"].composition_id == expected
    assert second.report_compositions["dataset-report-composition"].composition_id == expected


def test_ensure_report_composition_id_preserves_existing_identity() -> None:
    composition = InterpretationReportComposition(composition_id="rpt-custom")

    assert ensure_report_composition_id(composition, "dataset-report-composition") is composition


def test_ensure_report_composition_id_strips_explicit_identity() -> None:
    composition = InterpretationReportComposition(composition_id="  rpt-custom  ")

    canonical = ensure_report_composition_id(composition, "dataset-report-composition")

    assert canonical.composition_id == "rpt-custom"


def test_decoder_rejects_explicit_null_composition_id(tmp_path) -> None:
    project = _project()
    target = tmp_path / "null-composition-id.geolog.json"
    save_project(
        project,
        target,
        report_compositions={"dataset-report-composition": _composition()},
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["report_compositions"]["dataset-report-composition"]["composition_id"] = None
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(Exception, match="Некорректный ID report composition"):
        load_project_document(target)


def test_save_rejects_invalid_explicit_composition_id(tmp_path) -> None:
    with pytest.raises(ValueError, match="Некорректный ID report composition"):
        save_project(
            _project(),
            tmp_path / "invalid-composition-id.geolog.json",
            report_compositions={
                "dataset-report-composition": InterpretationReportComposition(
                    composition_id="x" * 129,
                )
            },
        )


def test_existing_v37_without_legend_mode_defaults_to_full(tmp_path) -> None:
    project = _project()
    target = tmp_path / "legacy-v37.geolog.json"

    save_project(
        project,
        target,
        report_compositions={"dataset-report-composition": _composition()},
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["report_compositions"]["dataset-report-composition"].pop("composition_id")
    payload["report_compositions"]["dataset-report-composition"].pop("legend_mode")
    payload["report_compositions"]["dataset-report-composition"].pop("headers")
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded = load_project_document(target)

    assert loaded.report_compositions["dataset-report-composition"].legend_mode is ReportLegendMode.FULL


def test_existing_v37_with_legend_but_without_headers_remains_readable(tmp_path) -> None:
    project = _project()
    target = tmp_path / "legacy-v37-legend.geolog.json"

    save_project(
        project,
        target,
        report_compositions={"dataset-report-composition": _composition()},
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["report_compositions"]["dataset-report-composition"].pop("composition_id")
    payload["report_compositions"]["dataset-report-composition"].pop("headers")
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded = load_project_document(target)
    composition = loaded.report_compositions["dataset-report-composition"]

    assert composition.legend_mode is ReportLegendMode.COMPACT
    assert composition.header_ru is None
    assert composition.header_kk is None
    assert composition.header_en is None


def test_localized_report_headers_are_isolated_by_language() -> None:
    base = InterpretationReportComposition()
    russian = ReportHeaderFields(report_title="Русский")
    english = ReportHeaderFields(report_title="English")

    composed = with_report_header_fields(base, "ru", russian)
    composed = with_report_header_fields(composed, "en", english)

    assert report_header_fields(composed, "ru", "standard") == russian
    assert report_header_fields(composed, "en", "standard") == english
    assert report_header_fields(composed, "kk", "standard") is None


def test_report_headers_are_isolated_by_profile() -> None:
    base = InterpretationReportComposition()
    standard = ReportHeaderFields(report_profile="standard", report_title="Standard")
    opus = ReportHeaderFields(report_profile="opus", report_title="OPUS")

    composed = with_report_header_fields(base, "en", standard)

    assert report_header_fields(composed, "en", "standard") == standard
    assert report_header_fields(composed, "en", "opus") is None

    composed = with_report_header_fields(composed, "en", opus)

    assert report_header_fields(composed, "en", "opus") == opus
    assert report_header_fields(composed, "en", "standard") is None


def test_legacy_v37_header_without_profile_defaults_to_standard(tmp_path) -> None:
    project = _project()
    target = tmp_path / "legacy-v37-header.geolog.json"
    save_project(
        project,
        target,
        report_compositions={"dataset-report-composition": _composition()},
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    header = payload["report_compositions"]["dataset-report-composition"]["headers"]["en"]
    header.pop("report_profile")
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded = load_project_document(target)
    restored = loaded.report_compositions["dataset-report-composition"].header_en

    assert restored is not None
    assert restored.report_profile == "standard"


def test_save_rejects_report_header_larger_than_decoder_limit(tmp_path) -> None:
    composition = with_report_header_fields(
        InterpretationReportComposition(),
        "en",
        ReportHeaderFields(report_title="x" * 2001),
    )

    with pytest.raises(ValueError, match="превышают допустимый размер"):
        save_project(
            _project(),
            tmp_path / "invalid-header.geolog.json",
            report_compositions={"dataset-report-composition": composition},
        )


def test_persisted_header_overlay_keeps_runtime_interval() -> None:
    identity = InterpretationReportIdentity(
        report_title="Custom title",
        report_subtitle="Custom subtitle",
        project_name="Project",
        well_name="Well",
        interval="1000–1100 m",
        revision="03",
    )
    header = report_header_fields_from_identity(identity)
    defaults = InterpretationReportIdentity(
        report_title="Default title",
        report_subtitle="Default subtitle",
        project_name="Project",
        well_name="Well",
        interval="2000–2100 m",
        revision="00",
    )

    restored = identity_with_report_header_fields(defaults, header)

    assert restored.report_title == "Custom title"
    assert restored.revision == "03"
    assert restored.interval == "2000–2100 m"


def test_project_v36_migrates_with_empty_report_compositions(tmp_path) -> None:
    project = _project()
    target = tmp_path / "legacy.geolog.json"
    save_project(project, target)

    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["format_version"] = 36
    payload.pop("report_compositions", None)
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded = load_project_document(target)

    assert loaded.report_compositions == {}


def test_save_rejects_report_composition_for_unknown_dataset(tmp_path) -> None:
    with pytest.raises(ValueError, match="неизвестный набор"):
        save_project(
            _project(),
            tmp_path / "invalid.geolog.json",
            report_compositions={"missing-dataset": _composition()},
        )


def test_package_round_trip_preserves_report_composition(tmp_path) -> None:
    document = ProjectDocument(
        project=_project(),
        report_compositions={"dataset-report-composition": _composition()},
    )
    target = tmp_path / "project.geologpkg"
    repository = PackageProjectRepository()

    repository.save(document, target)
    loaded = repository.load(target)

    assert loaded.report_compositions == document.report_compositions


def test_layout_dialog_restores_and_returns_persisted_composition(qapp) -> None:
    dialog = InterpretationPrintLayoutDialog(
        language=AppLanguage.EN,
        initial=_composition(),
    )
    try:
        assert dialog.orientation_combo.currentData() == QPageLayout.Orientation.Landscape
        layout = dialog.selected_layout()
        assert layout.order is InterpretationPrintOrder.LAST_TO_FIRST
        assert layout.geology_tracks.cuttings is GeologyTrackVisibility.SHOW
        assert layout.geology_tracks.lba is GeologyTrackVisibility.HIDE
        assert layout.legend_mode is ReportLegendMode.COMPACT
        assert ReportLegendMode(dialog.legend_mode_combo.currentData()) is ReportLegendMode.COMPACT
        assert dialog.selected_composition() == _composition()
    finally:
        dialog.close()


def test_project_controller_save_reopen_restores_report_composition(tmp_path) -> None:
    project = _project()
    session = ProjectSession(
        project=project,
        current_well_id="well-report-composition",
        current_dataset_id="dataset-report-composition",
        report_compositions={"dataset-report-composition": _composition()},
    )
    controller = ProjectController(session=session)
    target = tmp_path / "controller.geologpkg"

    controller.save_project(target)
    reopened = ProjectController().open_project(target)

    assert reopened.report_compositions == {
        "dataset-report-composition": _composition()
    }
    assert not reopened.dirty


def test_dataset_removal_paths_clear_report_compositions() -> None:
    sources = (
        inspect.getsource(DatasetMergeController._undo_command),
        inspect.getsource(DepthAxisController.undo_ascending_copy),
        inspect.getsource(DepthAxisController.undo_resample),
        inspect.getsource(DerivedDatasetController.rollback),
        inspect.getsource(LagCorrectionProjectController.delete_profile),
        inspect.getsource(TimeToDepthController.undo),
        inspect.getsource(TimeDepthAggregationController.undo),
    )

    assert all("report_compositions" in source for source in sources)
    assert all(".pop(" in source for source in sources)


def test_dataset_rebind_invalidates_preview_composition_cache() -> None:
    workspace_type = interpretation_report_workspace_final.InterpretationReportWorkspace
    source = inspect.getsource(workspace_type._sync_depth_interval_dataset)

    assert "self._preview_geology_report_key = None" in source



def test_workspace_propagates_persisted_legend_mode_to_preview_pdf_and_print() -> None:
    workspace_type = interpretation_report_workspace_final.InterpretationReportWorkspace
    preview_source = inspect.getsource(workspace_type._apply_chart_preview)
    pdf_source = inspect.getsource(workspace_type._export_pdf)
    print_source = inspect.getsource(workspace_type._print_report)

    assert "legend_mode=composition.legend_mode" in preview_source
    assert "legend_mode=layout.legend_mode" in pdf_source
    assert "legend_mode=layout.legend_mode" in print_source
    assert "with_report_header_fields(" in pdf_source
    assert "with_report_header_fields(" in print_source


def test_html_preview_legend_mode_hides_key_and_reaches_chart_renderer(monkeypatch) -> None:
    report = SimpleNamespace(analysis_depth_interval=None)
    dataset = object()
    seen: list[ReportLegendMode] = []

    monkeypatch.setattr(
        chart_front,
        "hydrocarbon_interpretation_html",
        lambda _report, _language: "<html><body><h2>Body</h2></body></html>",
    )
    monkeypatch.setattr(chart_front, "scope_dataset", lambda value, _interval: value)
    monkeypatch.setattr(
        chart_front,
        "interpretation_chart_key_html",
        lambda *_args, **_kwargs: "<h2>KEY</h2>",
    )
    monkeypatch.setattr(
        chart_front,
        "hydrocarbon_interpretation_chart_data_uri",
        lambda *_args, **kwargs: (
            seen.append(kwargs["legend_mode"]) or "data:image/png;base64,AA=="
        ),
    )
    from geoworkbench.services import hydrocarbon_interpretation_gas_html

    monkeypatch.setattr(
        hydrocarbon_interpretation_gas_html,
        "inject_interval_gas_statistics_html",
        lambda base, *_args, **_kwargs: base,
    )

    hidden = chart_front.hydrocarbon_interpretation_html_with_front_chart(
        report,
        dataset,
        AppLanguage.EN,
        legend_mode=ReportLegendMode.HIDE,
    )
    compact = chart_front.hydrocarbon_interpretation_html_with_front_chart(
        report,
        dataset,
        AppLanguage.EN,
        legend_mode=ReportLegendMode.COMPACT,
    )

    assert "<h2>KEY</h2>" not in hidden
    assert "<h2>KEY</h2>" in compact
    assert seen == [ReportLegendMode.HIDE, ReportLegendMode.COMPACT]


def test_preview_chart_uses_legend_mode_for_geology_legend_geometry() -> None:
    source = inspect.getsource(interpretation_chart.hydrocarbon_interpretation_chart_data_uri)

    assert "legend_mode is ReportLegendMode.HIDE" in source
    assert "legend_mode is ReportLegendMode.COMPACT" in source
    assert "compact=legend_compact" in source



def test_final_pdf_chart_pages_receive_same_legend_mode() -> None:
    renderer_source = inspect.getsource(pdf_renderer.render_hydrocarbon_interpretation_report)
    chart_source = inspect.getsource(pdf_chart.render_chart_pages)

    assert "legend_mode=legend_mode" in renderer_source
    assert "legend_mode is ReportLegendMode.HIDE" in chart_source
    assert "legend_mode is ReportLegendMode.COMPACT" in chart_source
    assert "compact=legend_compact" in chart_source


def test_compact_geology_legend_has_smaller_measured_height(qapp) -> None:
    legend = InterpretationGeologyLegend(
        tuple(
            GeologyLegendItem(
                "lithology",
                f"rock-{index}",
                f"R{index}",
                f"Lithology {index}",
            )
            for index in range(12)
        )
    )

    full = geology_legend_height(500.0, legend, compact=False)
    compact = geology_legend_height(500.0, legend, compact=True)

    assert compact < full
