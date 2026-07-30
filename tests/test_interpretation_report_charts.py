from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.printing.hydrocarbon_interpretation_chart import (
    hydrocarbon_interpretation_chart_data_uri,
    hydrocarbon_interpretation_html_with_chart,
)
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


def _session_with_report_curves() -> ProjectSession:
    depth = np.linspace(1_300.0, 1_420.0, 241)
    dataset = Dataset(
        "dataset",
        "Geology and technology",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    series = {
        "TG_CALC": 0.02 + 0.08 * np.exp(-((depth - 1_365.0) / 7.0) ** 2),
        "WH": 5.0 + 20.0 * np.exp(-((depth - 1_365.0) / 9.0) ** 2),
        "BH": 2.0 + 8.0 * np.exp(-((depth - 1_370.0) / 10.0) ** 2),
        "CH": 0.5 + 2.0 * np.exp(-((depth - 1_372.0) / 8.0) ** 2),
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


def test_whole_well_report_chart_is_embedded_in_html(qapp) -> None:
    session = _session_with_report_curves()
    dataset = session.current_dataset
    assert dataset is not None
    report = build_hydrocarbon_interpretation_report(session)

    uri = hydrocarbon_interpretation_chart_data_uri(report, dataset, AppLanguage.RU)
    html = hydrocarbon_interpretation_html_with_chart(report, dataset, AppLanguage.RU)

    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > 10_000
    assert "Графики интерпретационных кривых по глубине" in html
    assert "data:image/png;base64," in html


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

    assert exported == target
    assert target.read_bytes().startswith(b"%PDF")
    assert target.stat().st_size > 20_000


def test_workspace_exposes_primary_recalculation_and_chart_actions(qapp) -> None:
    workspace = InterpretationReportWorkspace(
        InterpretationCalculationController(ProjectSession()),
        language=AppLanguage.RU,
    )

    assert "Пересчитать все доступные кривые" in workspace.recalculate_all_button.text()
    assert workspace.refresh_chart_report_button.text() == "Обновить отчёт с графиками"
    report_index = workspace.report_mode.findData("well_text")
    assert report_index >= 0
    assert "с графиками" in workspace.report_mode.itemText(report_index)
    workspace.close()
