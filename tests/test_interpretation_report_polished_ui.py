from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace


def _add_curve(dataset: Dataset, mnemonic: str, value: float, unit: str) -> None:
    dataset.curves[mnemonic] = CurveData(
        CurveMetadata(
            curve_id=mnemonic,
            original_mnemonic=mnemonic,
            canonical_mnemonic=mnemonic,
            unit=unit,
            description=mnemonic,
            source_dataset_id=dataset.dataset_id,
        ),
        np.full(dataset.depth.shape, value, dtype=np.float64),
    )


def _controller() -> InterpretationCalculationController:
    dataset = Dataset(
        "polished-ui",
        "Polished UI",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.arange(2_000.0, 2_020.0),
    )
    for mnemonic, value, unit in (
        ("ROP", 60.0, "ft/h"),
        ("RPM", 100.0, "rpm"),
        ("WOB", 50_000.0, "lbf"),
        ("BIT", 10.0, "in"),
    ):
        _add_curve(dataset, mnemonic, value, unit)
    session = ProjectSession()
    session.add_dataset(dataset, "Well UI")
    controller = InterpretationCalculationController(session)
    controller.calculate_standard_curves()
    return controller


def test_polished_workspace_groups_controls_and_marks_primary_action(qapp) -> None:
    workspace = InterpretationReportWorkspace(_controller(), language=AppLanguage.RU)
    workspace.resize(1_500, 900)
    workspace.show()
    qapp.processEvents()

    assert workspace.intro_panel.objectName() == "interpretation-intro-panel"
    assert workspace.settings_panel.objectName() == "interpretation-settings-panel"
    assert workspace.dexp_quality_panel.objectName() == "dexp-quality-panel"
    assert workspace.analysis_settings_card.isVisible()
    assert workspace.reference_settings_card.isVisible()
    assert workspace.recalculate_all_button.property("role") == "primary"
    assert workspace.refresh_chart_report_button.property("role") == "secondary"
    assert workspace.configure_drilling_inputs_button.property("role") == "ghost"
    assert workspace.dexp_quality_progress.value() == 1_000
    assert "100,0%" in workspace.dexp_quality_summary.text()
    assert (
        workspace.recalculate_all_button.text()
        == "Пересчитать все доступные кривые и открыть планшет"
    )
    assert workspace.workflow_help_button is not None
    assert workspace.workflow_help_button.text() == "Настройка и печать"
    assert "пошаговая" in workspace.workflow_help_button.toolTip().casefold()
    guide = workspace._workflow_help_html()
    assert "Перспективные интервалы" in guide
    assert "Печать" in guide
    assert "Перспективных интервалов:" in workspace.status.text()
    workspace.close()


def test_polished_workspace_updates_dexp_gap_summary(qapp) -> None:
    controller = _controller()
    dataset = controller.session.current_dataset
    assert dataset is not None
    dexp = dataset.curve_by_mnemonic("DEXP")
    assert dexp is not None
    dexp.values[3:5] = np.nan

    workspace = InterpretationReportWorkspace(controller, language=AppLanguage.EN)
    workspace.show()
    qapp.processEvents()

    assert workspace.dexp_quality_progress.value() == 900
    assert "18 of 20" in workspace.dexp_quality_summary.text()
    assert "Missing points: 2" in workspace.dexp_quality_reasons.text()
    assert workspace.dexp_details_button.isEnabled()
    assert workspace.dexp_details_button.text() == "Gap details"
    workspace.close()


def test_report_export_progress_is_visible_and_blocks_repeat_actions(qapp) -> None:
    workspace = InterpretationReportWorkspace(_controller(), language=AppLanguage.RU)
    workspace.show()
    qapp.processEvents()

    assert workspace.export_progress.objectName() == "interpretation-report-export-progress"
    assert not workspace.export_progress.isVisible()
    with workspace._report_export_progress("Формируется Excel-отчёт…"):
        qapp.processEvents()
        assert workspace.export_progress.isVisible()
        assert workspace.export_progress.format() == "Формируется Excel-отчёт…"
        assert not workspace.xlsx_button.isEnabled()
        assert not workspace.docx_button.isEnabled()
        assert "Формируется Excel" in workspace.status.text()

    assert not workspace.export_progress.isVisible()
    assert workspace.xlsx_button.isEnabled()
    workspace.close()
