import numpy as np
from PySide6.QtWidgets import QPushButton, QTextBrowser

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.printing.interpretation_report import (
    build_interpretation_report,
    export_interpretation_report_pdf,
    interpretation_report_html,
)
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_dialog import InterpretationReportDialog


def _session() -> ProjectSession:
    session = ProjectSession()
    session.project.name = "Field <Alpha>"
    session.add_dataset(
        Dataset("dataset", "Depth log", DatasetKind.GTI, DepthDomain.MD, np.array([500.0, 520.0])),
        "Well 12",
    )
    controller = CuttingsController(session)
    controller.set_analysis(
        500.0,
        510.0,
        calcite_percent=62.5,
        dolomite_percent=17.5,
        lba_group=3,
        lba_intensity=4,
        lba_color="yellow-white",
        lba_cut="Streaming",
        lba_description="bright <direct> fluorescence",
        analysis_interpretation="Manual conclusion\nRequires correlation",
    )
    controller.set_analysis(510.0, 520.0, calcite_percent=40.0)
    return session


def test_interpretation_report_uses_source_results_and_manual_conclusion() -> None:
    report = build_interpretation_report(_session())

    assert report.project_name == "Field <Alpha>"
    assert report.well_name == "Well 12"
    assert report.dataset_name == "Depth log"
    assert report.calcimetry_count == 2
    assert report.lba_count == 1
    assert report.interpreted_count == 1
    first = report.entries[0]
    assert first.insoluble_residue_percent == 20.0
    assert ("intensity", "4") in first.lba_observations
    assert first.interpretation == "Manual conclusion\nRequires correlation"


def test_interpretation_report_html_is_localized_and_escapes_project_data() -> None:
    report = build_interpretation_report(_session())

    html = interpretation_report_html(report, AppLanguage.RU)
    english = interpretation_report_html(report, AppLanguage.EN)

    assert "Интерпретация кальциметрии и ЛБА" in html
    assert "Нерастворимый остаток: 20%" in html
    assert "Интенсивность: 4" in html
    assert "Field &lt;Alpha&gt;" in html
    assert "bright &lt;direct&gt; fluorescence" in html
    assert "This report is not an automatic conclusion" in english


def test_interpretation_report_exports_pdf(qapp, tmp_path) -> None:
    report = build_interpretation_report(_session())
    target = tmp_path / "interpretation.pdf"

    exported = export_interpretation_report_pdf(report, target, language=AppLanguage.EN)

    assert exported == target
    assert target.read_bytes().startswith(b"%PDF")
    assert target.stat().st_size > 1000


def test_interpretation_report_dialog_previews_report(qapp) -> None:
    dialog = InterpretationReportDialog(_session(), language=AppLanguage.EN)

    preview = dialog.findChild(QTextBrowser, "interpretation-report-preview")
    export_button = dialog.findChild(QPushButton, "interpretation-report-export")

    assert preview is not None
    assert "Manual conclusion" in preview.toPlainText()
    assert export_button is not None and export_button.text() == "Export PDF..."
    dialog.close()
