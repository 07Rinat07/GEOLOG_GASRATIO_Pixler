from pathlib import Path
import json
from unicodedata import normalize

import fitz
import numpy as np
import pytest
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QDialog

from geoworkbench.printing import hydrocarbon_interpretation_chart as preview_renderer
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as pdf_renderer
from geoworkbench.printing.report_annotation_rendering import paint_report_annotations
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.interpretation_calculation_controller import InterpretationCalculationController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_passport import passport_sidecar_path
from geoworkbench.ui import interpretation_report_workspace_final as final
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace
from test_report_annotations_multiwell_acceptance import PAIRS, _select, _two_well_session


def _text(path):
    with fitz.open(path) as document:
        return "".join(normalize("NFKC", page.get_text()) for page in document).replace(" ", "").replace("\n", "")


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("suffix", (".geolog.json", ".geologpkg"))
def test_composer_annotations_survive_reopen_in_preview_pdf_and_system_print(
    qapp, tmp_path: Path, monkeypatch, language: AppLanguage, suffix: str,
) -> None:
    session = _two_well_session()
    for well_id, dataset_id, _ in PAIRS:
        dataset = session.project.wells[well_id].datasets[dataset_id]
        dataset.upsert_curve("TG", np.array([5.0, 10.0, 15.0]), unit="%", provenance="source")
    raw = {
        dataset_id: (dataset.depth.copy(), {key: curve.values.copy() for key, curve in dataset.curves.items()})
        for well in session.project.wells.values()
        for dataset_id, dataset in well.datasets.items()
    }
    labels = {AppLanguage.RU: "Заметка", AppLanguage.KK: "Белгі", AppLanguage.EN: "Note"}
    notes = {dataset_id: f"{labels[language]} {index}" for index, (_, dataset_id, _) in enumerate(PAIRS)}
    records = {}
    dialogs = []
    workspace = InterpretationReportWorkspace(InterpretationCalculationController(session), language=language)

    def edit(dialog):
        dialogs.append(dialog)
        assert dialog.parent() is workspace
        assert dialog.controller.available() == ()
        dataset_id = session.current_dataset_id
        dialog.track.setCurrentText("curve:TG")
        dialog.depth_spin.setValue(float(session.current_dataset.depth[1]))
        dialog.text.setText(notes[dataset_id])
        dialog.add_button.click()
        dialog.annotation.setCurrentIndex(0)
        dialog.track.setCurrentText("curve:ABSENT")
        dialog.depth_spin.setValue(float(session.current_dataset.depth[1]))
        dialog.text.setText("MISSING TRACK NOTE")
        dialog.add_button.click()
        records[dataset_id] = dialog.controller.available()
        assert len(records[dataset_id]) == 2
        dialog.accept()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(final.InterpretationReportAnnotationDialog, "exec", edit)
    observed = []

    def capture(renderer):
        def paint(painter, annotations, output_language, **kwargs):
            count = paint_report_annotations(painter, annotations, output_language, **kwargs)
            observed.append((renderer, tuple(annotations), output_language, count))
            return count
        return paint

    try:
        for well_id, dataset_id, _ in PAIRS:
            _select(session, well_id, dataset_id)
            workspace.refresh()
            workspace.report_annotations_button.click()
            assert workspace._report_composition().annotations == records[dataset_id]
        assert len(dialogs) == 2
        target = tmp_path / ("composer-output" + suffix)
        ProjectController(session=session).save_project(target)
        for dialog in dialogs:
            dialog.deleteLater()
        workspace.close()
        workspace.deleteLater()
        qapp.processEvents()
        dialogs.clear()
        session = ProjectController().open_project(target)
        workspace = InterpretationReportWorkspace(InterpretationCalculationController(session), language=language)
        monkeypatch.setattr(preview_renderer, "paint_report_annotations", capture("preview"))
        monkeypatch.setattr(pdf_renderer, "paint_report_annotations", capture("pdf"))
        monkeypatch.setattr(final.InterpretationReportDetailsDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
        monkeypatch.setattr(final.InterpretationPrintLayoutDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
        monkeypatch.setattr(workspace, "_show_export_success", lambda *args: None)
        monkeypatch.setattr(workspace, "_show_export_error", lambda error: pytest.fail(str(error)))
        original_export = final.export_hydrocarbon_interpretation_pdf
        prepared = tmp_path / "prepared.pdf"

        def export(report, path, **kwargs):
            assert kwargs["annotations"] == records[session.current_dataset_id]
            result = original_export(report, path, **kwargs)
            prepared.write_bytes(Path(result).read_bytes())
            return result

        monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf", export)
        printed = tmp_path / "printed.pdf"

        class PrintDialog(final.QPrintDialog):
            def __init__(self, printer, parent):
                super().__init__(printer, parent)
                self.target_printer = printer

            def exec(self):
                self.target_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                self.target_printer.setOutputFileName(str(printed))
                self.target_printer.setResolution(150)
                return QDialog.DialogCode.Accepted

        monkeypatch.setattr(final, "QPrintDialog", PrintDialog)
        for well_id, dataset_id, _ in PAIRS:
            _select(session, well_id, dataset_id)
            observed.clear()
            workspace.refresh()
            assert workspace._report_composition().annotations == records[dataset_id]
            assert any(renderer == "preview" and count == 1 for renderer, _, _, count in observed)
            pdf = tmp_path / (dataset_id + ".pdf")
            monkeypatch.setattr(workspace, "_choose_target", lambda *args, pdf=pdf: pdf)
            workspace._export_pdf()
            passport = json.loads(passport_sidecar_path(pdf).read_text(encoding="utf-8"))
            assert passport["language"] == language.value
            assert dict(passport["render"]["options"])["report_annotations"] == "2"
            workspace._print_report()
            for output in (pdf, prepared):
                text = _text(output)
                assert notes[dataset_id].replace(" ", "") in text
                other_id = "dataset-b" if dataset_id == "dataset-a" else "dataset-a"
                assert notes[other_id].replace(" ", "") not in text
                assert "MISSINGTRACKNOTE" not in text
            assert any(renderer == "pdf" and count == 1 for renderer, _, _, count in observed)
            assert all(snapshot == records[dataset_id] and output_language is language for _, snapshot, output_language, _ in observed)
            with fitz.open(printed) as document:
                assert len(document) > 0
                assert all(page.get_images() for page in document)
            dataset = session.current_dataset
            expected_depth, curves = raw[dataset_id]
            np.testing.assert_array_equal(dataset.depth, expected_depth)
            for key, values in curves.items():
                np.testing.assert_array_equal(dataset.curves[key].values, values)
        assert records["dataset-a"][0].scope_id != records["dataset-b"][0].scope_id
    finally:
        for dialog in dialogs:
            dialog.deleteLater()
        workspace.close()
        workspace.deleteLater()
        qapp.processEvents()
