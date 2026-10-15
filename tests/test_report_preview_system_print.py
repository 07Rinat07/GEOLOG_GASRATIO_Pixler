"""Direct system printing uses persisted PDF preview page marks exactly once."""

from __future__ import annotations

from pathlib import Path

import fitz
import numpy as np
import pytest
from PySide6.QtWidgets import QDialog

from geoworkbench.domain.report_composition import (
    InterpretationReportComposition,
    ensure_report_composition_id,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_preview_marks import PreviewMark, PreviewMarkKind
from geoworkbench.ui import interpretation_report_workspace_final as final
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace
from test_report_annotations_multiwell_acceptance import _select, _two_well_session


@pytest.mark.parametrize("well_id,dataset_id", (
    ("well-a", "dataset-a"), ("well-b", "dataset-b"),
))
def test_direct_system_print_uses_own_saved_marks_without_altering_source(
    qapp, tmp_path, monkeypatch, well_id, dataset_id,
):
    session = _two_well_session()
    for owner_id, owner_dataset in (
        ("well-a", "dataset-a"), ("well-b", "dataset-b"),
    ):
        mark = PreviewMark(
            PreviewMarkKind.COMMENT, 1, 0.15, 0.3, text=f"Print {owner_id}",
        )
        session.report_compositions[owner_dataset] = ensure_report_composition_id(
            InterpretationReportComposition(preview_marks=(mark,)), owner_dataset,
        )
    _select(session, well_id, dataset_id)
    dataset = session.current_dataset
    assert dataset is not None
    raw_depth = dataset.depth.copy()
    raw_curves = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    workspace = InterpretationReportWorkspace(
        InterpretationCalculationController(session), language=AppLanguage.RU,
    )
    rendered_source = []
    observed = []

    def export_pdf(_report, path, **kwargs):
        with fitz.open() as doc:
            for number in range(2):
                page = doc.new_page()
                page.insert_text((72, 72), f"Printed source page {number + 1}")
            doc.save(path)
        rendered_source.append(Path(path).read_bytes())
        return Path(path)

    def print_pages(pdf, _printer, pages, **_kwargs):
        with fitz.open(pdf) as doc:
            observed.append((
                tuple(pages),
                tuple(len(page.get_images(full=True)) for page in doc),
                doc[0].get_text(),
                doc[1].get_text(),
            ))
        return True

    class AcceptedPrintDialog(final.QPrintDialog):
        def exec(self):
            return QDialog.DialogCode.Accepted

    try:
        workspace.refresh()
        monkeypatch.setattr(
            final.InterpretationReportDetailsDialog, "exec",
            lambda self: QDialog.DialogCode.Accepted,
        )
        monkeypatch.setattr(
            final.InterpretationPrintLayoutDialog, "exec",
            lambda self: QDialog.DialogCode.Accepted,
        )
        monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf", export_pdf)
        monkeypatch.setattr(final, "print_pdf_page_selection", print_pages)
        monkeypatch.setattr(final, "QPrintDialog", AcceptedPrintDialog)
        monkeypatch.setattr(
            workspace, "_show_export_error", lambda error: pytest.fail(str(error)),
        )
        workspace._print_report()
        assert len(rendered_source) == 1
        assert observed
        selected_pages, images, page_one, page_two = observed[0]
        assert selected_pages
        assert images == (0, 1)
        assert "Printed source page 1" in page_one
        assert "Printed source page 2" in page_two
        with fitz.open(stream=rendered_source[0], filetype="pdf") as source:
            assert not source[0].get_images(full=True)
            assert not source[1].get_images(full=True)
        np.testing.assert_array_equal(dataset.depth, raw_depth)
        for key, values in raw_curves.items():
            np.testing.assert_array_equal(dataset.curves[key].values, values)
    finally:
        workspace.close()
        workspace.deleteLater()
        qapp.processEvents()


def test_direct_print_rejects_missing_mark_page_before_opening_printer(
    qapp, monkeypatch,
):
    session = _two_well_session()
    session.report_compositions["dataset-a"] = ensure_report_composition_id(
        InterpretationReportComposition(
            preview_marks=(PreviewMark(
                PreviewMarkKind.TEXT, 99, 0.2, 0.3, text="Out of range",
            ),),
        ),
        "dataset-a",
    )
    workspace = InterpretationReportWorkspace(
        InterpretationCalculationController(session), language=AppLanguage.EN,
    )
    errors = []
    print_called = []

    def export_pdf(_report, path, **_kwargs):
        with fitz.open() as doc:
            doc.new_page()
            doc.save(path)
        return Path(path)

    try:
        workspace.refresh()
        monkeypatch.setattr(
            final.InterpretationReportDetailsDialog, "exec",
            lambda self: QDialog.DialogCode.Accepted,
        )
        monkeypatch.setattr(
            final.InterpretationPrintLayoutDialog, "exec",
            lambda self: QDialog.DialogCode.Accepted,
        )
        monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf", export_pdf)
        monkeypatch.setattr(final, "QPrintDialog", lambda *args: print_called.append(True))
        monkeypatch.setattr(workspace, "_show_export_error", errors.append)
        workspace._print_report()
        assert len(errors) == 1
        assert "missing PDF page" in str(errors[0])
        assert not print_called
    finally:
        workspace.close()
        workspace.deleteLater()
        qapp.processEvents()
