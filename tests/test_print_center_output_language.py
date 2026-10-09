from copy import deepcopy
from dataclasses import replace
import json
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unicodedata import normalize

import fitz
import numpy as np
import pyqtgraph as pg
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QImage
from PySide6.QtPrintSupport import QPrinter

from geoworkbench.printing.print_job import (
    PrintExportPreferences,
    PrintOutputFormat,
)
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.dataset_export_controller import DatasetExportController
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.print_jobs import PrintJobExecutor
from geoworkbench.services.report_definition import ReportIntervalContext
from geoworkbench.services.report_passport import ReportPassportBuilder
from geoworkbench.services.user_profiles import UserProfileSettings
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView
from geoworkbench.ui.main_window import MainWindow
from geoworkbench.ui.print_center_dialog import PrintCenterDialog
from geoworkbench.visualization.curve_view import CurveView
from test_interpretation_report import _session


def _compact(text):
    return "".join(normalize("NFKC", text).split())


def _pdf_text(path):
    with fitz.open(path) as pdf:
        return " ".join(page.get_text() for page in pdf)


def _assert_pdf_language(path, language):
    with fitz.open(path) as pdf:
        for index, page in enumerate(pdf, start=1):
            footer = Localizer.create(language).text(
                "print_center.page_number", page=index, total=len(pdf)
            )
            assert _compact(footer) in _compact(page.get_text())
        return len(pdf)


@pytest.mark.parametrize("ui_language", list(AppLanguage))
@pytest.mark.parametrize("output_language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["tablet", "curves"])
def test_print_center_persisted_language_reaches_real_outputs_and_passport(
    qapp, tmp_path, ui_language, output_language, kind
):
    session = _session()
    project = tmp_path / "print.geologpkg"
    ProjectController(session=session).save_project(project)
    session = ProjectController().open_project(project)
    dataset = session.current_dataset
    before = deepcopy(dataset)
    if kind == "tablet":
        source = TabletView(language=ui_language)
        source.set_layout_and_dataset(
            TabletLayout(
                tracks=[
                    TrackDefinition("depth", "Глубина", TrackKind.DEPTH, width=100),
                    TrackDefinition(
                        "gas", "C1", TrackKind.CURVE, width=180, curve_mnemonics=["C1"]
                    ),
                ]
            ),
            dataset,
        )
        source.set_visible_depth(500, 520)
    else:
        source = CurveView(language=ui_language)
        source.show_dataset(dataset, ["C1"])
        source._curve_items[dataset.curve_by_mnemonic("C1").metadata.curve_id].setPen(
            pg.mkPen("#8030a0", width=2.5)
        )
        source.selection.select(dataset, 505, 510)
        source.show_cursor_at_depth(508)
    source.resize(800, 600)
    source.show()
    qapp.processEvents()
    harness = SimpleNamespace(
        session=session,
        language=ui_language,
        dataset_export_controller=DatasetExportController(session),
        report_passport_builder=ReportPassportBuilder(),
    )
    for method in ("_print_report_curve_ids", "_print_report_channel_mnemonics"):
        setattr(harness, method, getattr(MainWindow, method).__get__(harness))
    settings = UserProfileSettings(
        QSettings(str(tmp_path / "profile.ini"), QSettings.Format.IniFormat)
    )
    settings.create("Engineer")
    dialog = PrintCenterDialog(
        language=ui_language,
        initial_preferences=PrintExportPreferences(output_format=PrintOutputFormat.PDF, dpi=96),
        printer_choices=(("Test printer", True),),
    )
    reopened = None
    try:
        dialog.report_output_language.setCurrentIndex(
            dialog.report_output_language.findData(output_language)
        )
        settings.save_print_export_preferences_for_form("form-a", dialog.preferences())
        persisted = UserProfileSettings(
            QSettings(str(tmp_path / "profile.ini"), QSettings.Format.IniFormat)
        ).print_export_preferences_for_form("form-a")
        assert persisted.output_language == output_language
        reopened = PrintCenterDialog(
            language=ui_language,
            initial_preferences=persisted,
            printer_choices=(("Test printer", True),),
        )
        reopened.path_input.setText(str(tmp_path / "report.pdf"))
        reopened.resize(900, 650)
        reopened.show()
        qapp.processEvents()
        assert reopened.localizer.language == ui_language
        assert reopened.report_output_language.currentData() == output_language
        assert reopened.report_output_language_label.buddy() is reopened.report_output_language
        job = reopened.job_settings()
        assert job.output_language == output_language
        captures = []
        reopened.preview_callback = captures.append
        reopened._preview()
        assert captures[0].output_language == output_language
        context = ReportIntervalContext(current_range=(500, 520), full_range=(500, 520))
        report, normalized = MainWindow._resolve_print_report(
            harness, source, job, "Authored title Әғқң", report_context=context
        )
        assert report.definition.language == output_language.value
        passport = MainWindow._build_print_passport(
            harness, report, normalized, "Authored title Әғқң"
        )
        assert passport.language == output_language.value
        executor = PrintJobExecutor()
        result = executor.execute_file(
            source,
            normalized,
            source_name="Authored title Әғқң",
            language=ui_language,
            passport=passport,
            session=session,
        )
        assert _assert_pdf_language(result.paths[0], output_language) == result.page_count
        payload = json.loads(result.passport_path.read_text(encoding="utf-8"))
        assert payload["language"] == output_language.value
        for mode in ("preview", "printer"):
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(str(tmp_path / (mode + ".pdf")))
            printer.setResolution(96)
            printer_job = replace(normalized, output_format=PrintOutputFormat.PRINTER, target=None)
            if mode == "preview":
                executor.render_preview(
                    source,
                    printer,
                    printer_job,
                    source_name="Authored title Әғқң",
                    language=ui_language,
                    session=session,
                )
            else:
                executor.render_to_printer(
                    source,
                    printer,
                    printer_job,
                    source_name="Authored title Әғқң",
                    language=ui_language,
                    session=session,
                )
            _assert_pdf_language(tmp_path / (mode + ".pdf"), output_language)
        for output in (PrintOutputFormat.PNG, PrintOutputFormat.SVG):
            file_job = replace(
                normalized, output_format=output, target=tmp_path / ("report" + output.suffix)
            )
            file_report, file_job = MainWindow._resolve_print_report(
                harness, source, file_job, "Authored title Әғқң", report_context=context
            )
            file_passport = MainWindow._build_print_passport(
                harness, file_report, file_job, "Authored title Әғқң"
            )
            image_result = executor.execute_file(
                source,
                file_job,
                source_name="Authored title Әғқң",
                language=ui_language,
                passport=file_passport,
                session=session,
            )
            assert (
                json.loads(image_result.passport_path.read_text(encoding="utf-8"))["language"]
                == output_language.value
            )
            if output == PrintOutputFormat.PNG:
                assert not QImage(str(image_result.paths[0])).isNull()
            else:
                for index, path in enumerate(image_result.paths, start=1):
                    root = ET.fromstring(path.read_bytes())
                    text = " ".join(root.itertext())
                    footer = Localizer.create(output_language).text(
                        "print_center.page_number", page=index, total=image_result.page_count
                    )
                    assert _compact(footer) in _compact(text)
        if kind == "tablet":
            assert source._localizer.language == ui_language
            assert source.visible_depth_range == (500, 520)
        else:
            assert source.localizer.language == ui_language
            assert source.selection.interval == (505, 510)
            assert source._last_cursor_depth == 508
            pen = source._curve_items[dataset.curve_by_mnemonic("C1").metadata.curve_id].opts["pen"]
            assert pen.color().name() == "#8030a0"
        np.testing.assert_array_equal(dataset.depth, before.depth)
        for key, curve in dataset.curves.items():
            np.testing.assert_array_equal(curve.values, before.curves[key].values)
    finally:
        for widget in (dialog, reopened, source):
            if widget is not None:
                widget.close()
                widget.deleteLater()
        qapp.processEvents()


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["tablet", "curves"])
def test_print_clone_translates_content_and_preserves_live_state(qapp, language, kind):
    session = _session()
    dataset = session.current_dataset
    source = (
        TabletView(language=AppLanguage.RU)
        if kind == "tablet"
        else CurveView(language=AppLanguage.RU)
    )
    if kind == "tablet":
        source.set_layout_and_dataset(
            TabletLayout(
                tracks=[
                    TrackDefinition("depth", "Глубина", TrackKind.DEPTH, width=100),
                    TrackDefinition(
                        "gas", "Authored C1", TrackKind.CURVE, width=180, curve_mnemonics=["C1"]
                    ),
                ]
            ),
            dataset,
        )
        source.set_visible_depth(502, 514)
    else:
        source.show_dataset(dataset, ["C1"])
        source._plot.setRange(xRange=(4, 16), yRange=(502, 514), padding=0)
        source.selection.select(dataset, 505, 510)
        source.show_cursor_at_depth(508)
        curve_id = dataset.curve_by_mnemonic("C1").metadata.curve_id
        source._curve_items[curve_id].setPen(pg.mkPen("#8030a0", width=2.5))
    source.resize(800, 600)
    source.show()
    qapp.processEvents()
    clone = source.create_print_clone(language=language)
    try:
        assert clone.property("geoworkbench-print-clone") is True
        if kind == "tablet":
            assert clone._localizer.language == language
            assert source._localizer.language == AppLanguage.RU
            assert clone.visible_depth_range == source.visible_depth_range
            assert clone._dataset is source._dataset
            assert clone.layout_model.tracks[1].title == "Authored C1"
        else:
            assert clone.localizer.language == language
            assert source.localizer.language == AppLanguage.RU
            assert clone._plot.getAxis("left").labelText == Localizer.create(language).text(
                "curve.axis.depth"
            )
            assert clone._dataset is source._dataset
            assert clone.selection is not source.selection
            assert clone.selection.interval == source.selection.interval
            assert clone._last_cursor_depth == source._last_cursor_depth
            np.testing.assert_allclose(clone._plot.viewRange(), source._plot.viewRange())
            pen = clone._curve_items[curve_id].opts["pen"]
            assert pen.color().name() == "#8030a0"
            assert pen.widthF() == 2.5
    finally:
        clone.close()
        clone.deleteLater()
        source.close()
        source.deleteLater()
        qapp.processEvents()
