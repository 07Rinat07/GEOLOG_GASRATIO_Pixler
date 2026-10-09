from copy import deepcopy
from html import escape
from pathlib import Path
from unicodedata import normalize
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import fitz
import numpy as np
from openpyxl import load_workbook
import pytest

from geoworkbench.printing import interpretation_report as core
from geoworkbench.printing.interpretation_report import _LABELS
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import interpretation_report_dialog as ui
from test_interpretation_report import _session


def _text(path: Path) -> str:
    if path.suffix == ".pdf":
        with fitz.open(path) as document:
            return " ".join(page.get_text() for page in document)
    if path.suffix == ".docx":
        with ZipFile(path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
        return " ".join(
            node.text or ""
            for node in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
        )
    book = load_workbook(path, data_only=True)
    try:
        return " ".join(
            str(cell.value)
            for sheet in book
            for row in sheet
            for cell in row
            if cell.value is not None
        )
    finally:
        book.close()


def _compact(value: str) -> str:
    return "".join(normalize("NFKC", value).split())


@pytest.mark.parametrize("ui_language", list(AppLanguage))
@pytest.mark.parametrize("output_language", list(AppLanguage))
def test_reopened_geology_dialog_exports_entire_selected_snapshot(
    qapp, tmp_path, monkeypatch, ui_language, output_language
):
    session = _session()
    well = session.current_well
    fields = ("description_i18n", "lba_description_i18n", "analysis_interpretation_i18n")
    for field in fields:
        setattr(
            well.cuttings[0],
            field,
            {
                lang.value: (
                    "<p>" + escape(f"{lang.value}-{field} Әғқң <&>") + "</p>"
                    if field == "description_i18n"
                    else f"{lang.value}-{field} Әғқң <&>"
                )
                for lang in AppLanguage
            },
        )
    for field in ("name_i18n", "description_i18n"):
        setattr(
            well.stratigraphy[0],
            field,
            {lang.value: f"{lang.value}-stratigraphy-{field} Әғқң <&>" for lang in AppLanguage},
        )
    project = tmp_path / "geology.geologpkg"
    ProjectController(session=session).save_project(project)
    session = ProjectController().open_project(project)
    before_well = deepcopy(session.current_well)
    before_dataset = deepcopy(session.current_dataset)
    numerical_builds = []
    meter_builds = []
    original_index = core.IntervalGasStatisticsIndex
    original_meters = core._build_meter_geology

    def counted_index(*args, **kwargs):
        numerical_builds.append(True)
        return original_index(*args, **kwargs)

    def counted_meters(*args, **kwargs):
        meter_builds.append(True)
        return original_meters(*args, **kwargs)

    monkeypatch.setattr(core, "IntervalGasStatisticsIndex", counted_index)
    monkeypatch.setattr(core, "_build_meter_geology", counted_meters)
    original_builder = ui.build_interpretation_report
    builds = []

    def counted_builder(*args, **kwargs):
        builds.append(kwargs["language"])
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(ui, "build_interpretation_report", counted_builder)
    dialog = ui.InterpretationReportDialog(session, language=ui_language)
    assert builds == [ui_language]
    assert len(numerical_builds) == len(meter_builds) == 1
    try:
        snapshots = deepcopy(dialog._reports_by_language)
        initial = dialog.report
        monkeypatch.setattr(
            ui,
            "build_interpretation_report",
            lambda *args, **kwargs: pytest.fail("Language selection rebuilt the report"),
        )
        dialog.report_output_language.setCurrentIndex(
            dialog.report_output_language.findData(output_language)
        )
        assert dialog.language == ui_language
        assert dialog.report is dialog._reports_by_language[output_language]
        dialog.resize(720, 420)
        dialog.show()
        qapp.processEvents()
        assert dialog.report_output_language.isVisible()
        assert dialog.report_output_language_label.buddy() is dialog.report_output_language
        markers = [f"{output_language.value}-{field} Әғқң <&>" for field in fields]
        markers += [
            f"{output_language.value}-stratigraphy-{field} Әғқң <&>"
            for field in ("name_i18n", "description_i18n")
        ]

        def assert_language(text):
            compact = _compact(text)
            for marker in markers:
                assert _compact(marker) in compact
            assert _compact(_LABELS[output_language]["title"]) in compact
            for lang in AppLanguage:
                if lang != output_language:
                    assert f"{lang.value}-analysis_interpretation_i18n" not in compact

        assert_language(dialog.preview.toPlainText())
        monkeypatch.setattr(ui.QMessageBox, "information", lambda *args: None)
        monkeypatch.setattr(ui.QMessageBox, "critical", lambda *args: pytest.fail(str(args)))
        for suffix, method in (
            (".pdf", "_export_pdf"),
            (".docx", "_export_docx"),
            (".xlsx", "_export_xlsx"),
        ):
            target = tmp_path / ("geology" + suffix)
            monkeypatch.setattr(
                ui.QFileDialog, "getSaveFileName", lambda *args, target=target: (str(target), "")
            )
            getattr(dialog, method)()
            assert_language(_text(target))
        for snapshot in snapshots.values():
            assert snapshot.sample_count == initial.sample_count
            assert tuple(
                (
                    entry.top_depth,
                    entry.bottom_depth,
                    entry.calcite_percent,
                    entry.dolomite_percent,
                    entry.gas_statistics,
                    entry.lba_standard_assessment,
                )
                for entry in snapshot.entries
            ) == tuple(
                (
                    entry.top_depth,
                    entry.bottom_depth,
                    entry.calcite_percent,
                    entry.dolomite_percent,
                    entry.gas_statistics,
                    entry.lba_standard_assessment,
                )
                for entry in initial.entries
            )
        for snapshot in dialog._reports_by_language.values():
            for entry, source in zip(snapshot.entries, initial.entries, strict=True):
                assert entry.gas_statistics is source.gas_statistics
                assert entry.rock_components is source.rock_components
                assert entry.lba_standard_assessment is source.lba_standard_assessment
            for meter, source in zip(snapshot.meter_geology, initial.meter_geology, strict=True):
                assert meter.rock_components is source.rock_components
                assert meter.sample_intervals is source.sample_intervals
        assert dialog._reports_by_language == snapshots
        assert session.current_well.cuttings == before_well.cuttings
        assert session.current_well.stratigraphy == before_well.stratigraphy
        assert session.current_well.name == before_well.name
        np.testing.assert_array_equal(session.current_dataset.depth, before_dataset.depth)
        for key, curve in session.current_dataset.curves.items():
            np.testing.assert_array_equal(curve.values, before_dataset.curves[key].values)
        session.current_well.cuttings[0].analysis_interpretation_i18n[output_language.value] = (
            "Later project edit"
        )
        for lang in AppLanguage:
            dialog.report_output_language.setCurrentIndex(
                dialog.report_output_language.findData(lang)
            )
        dialog.report_output_language.setCurrentIndex(
            dialog.report_output_language.findData(output_language)
        )
        assert_language(dialog.preview.toPlainText())
        assert dialog._reports_by_language == snapshots
        assert len(numerical_builds) == len(meter_builds) == 1
    finally:
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()


@pytest.mark.parametrize("ui_language", list(AppLanguage))
def test_geology_cancel_keeps_ui_language_and_creates_no_output(qapp, monkeypatch, ui_language):
    dialog = ui.InterpretationReportDialog(_session(), language=ui_language)
    try:
        dialog.report_output_language.setCurrentIndex(
            dialog.report_output_language.findData(AppLanguage.EN)
        )
        monkeypatch.setattr(ui.QFileDialog, "getSaveFileName", lambda *args: ("", ""))
        for name in (
            "export_interpretation_report_pdf",
            "export_interpretation_report_docx",
            "export_interpretation_report_xlsx",
        ):
            monkeypatch.setattr(
                ui, name, lambda *args, **kwargs: pytest.fail("Cancelled export wrote output")
            )
        for method in (dialog._export_pdf, dialog._export_docx, dialog._export_xlsx):
            method()
        assert dialog.windowTitle() == dialog.localizer.text("interpretation_report.title")
        assert dialog.export_button.text() == dialog.localizer.text("interpretation_report.export")
    finally:
        dialog.close()


@pytest.mark.parametrize("ui_language", list(AppLanguage))
def test_geology_export_failure_uses_ui_language(qapp, tmp_path, monkeypatch, ui_language):
    dialog = ui.InterpretationReportDialog(_session(), language=ui_language)
    try:
        dialog.report_output_language.setCurrentIndex(
            dialog.report_output_language.findData(AppLanguage.EN)
        )
        monkeypatch.setattr(
            ui.QFileDialog, "getSaveFileName", lambda *args: (str(tmp_path / "failed.docx"), "")
        )
        messages = []
        monkeypatch.setattr(
            ui.QMessageBox,
            "critical",
            lambda parent, title, message: messages.append((title, message)),
        )

        def fail_export(*args, **kwargs):
            assert kwargs["language"] == AppLanguage.EN
            raise ui.InterpretationReportOfficeError("Output unavailable")

        monkeypatch.setattr(ui, "export_interpretation_report_docx", fail_export)
        dialog._export_docx()
        assert messages == [
            (dialog.localizer.text("interpretation_report.title"), "Output unavailable")
        ]
        assert not (tmp_path / "failed.docx").exists()
    finally:
        dialog.close()


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("duplicate_interval", [False, True])
def test_localized_projection_matches_full_build(language, duplicate_interval):
    session = _session()
    if duplicate_interval:
        sample = deepcopy(session.current_well.cuttings[0])
        sample.sample_id = "duplicate-interval"
        session.current_well.cuttings.append(sample)
    for index, sample in enumerate(session.current_well.cuttings):
        for field in ("description_i18n", "lba_description_i18n", "analysis_interpretation_i18n"):
            setattr(
                sample,
                field,
                {lang.value: f"Sample {index}: {lang.value} {field}" for lang in AppLanguage},
            )
    for interval in session.current_well.stratigraphy:
        interval.description_i18n = {
            lang.value: f"{interval.interval_id}: {lang.value}" for lang in AppLanguage
        }
    source = core.build_interpretation_report(session, language=AppLanguage.RU)
    projected = core.localize_interpretation_report(source, session, language)
    expected = core.build_interpretation_report(session, language=language)
    assert projected == expected
