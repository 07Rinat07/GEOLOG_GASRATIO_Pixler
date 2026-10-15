"""Preview page marks survive production JSON/package project reopening.

The preview-only edit history is transient; confirmed overlay state is
presentation metadata on each dataset's report composition.
"""

from __future__ import annotations

from dataclasses import replace
import json

import fitz
import numpy as np
import pytest
from PySide6.QtWidgets import QInputDialog

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.domain.report_composition import (
    InterpretationReportComposition,
    ensure_report_composition_id,
)
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_preview_marks import (
    PreviewMark,
    PreviewMarkKind,
    preview_marks_from_list,
    preview_marks_to_list,
)
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import ProjectFormatError, load_project_document
from geoworkbench.ui.interpretation_full_report_preview import FullReportPreviewDialog


def _session() -> ProjectSession:
    wells = {}
    for well_id, dataset_id, start in (
        ("well-a", "dataset-a", 1000.0),
        ("well-b", "dataset-b", 2000.0),
    ):
        ds = Dataset(
            dataset_id, dataset_id, DatasetKind.GTI, DepthDomain.MD,
            np.asarray([start, start + 1.0, start + 2.0]),
        )
        ds.upsert_curve("TG", np.asarray([0.1, 0.2, 0.3]), unit="%")
        wells[well_id] = Well(well_id, well_id, {dataset_id: ds})
    return ProjectSession(
        Project("project-preview-marks", "Preview", wells=wells),
        "well-a", "dataset-a",
    )


def _mark(label: str, page: int = 0) -> PreviewMark:
    return PreviewMark(PreviewMarkKind.TEXT, page, 0.25, 0.45, text=label)


@pytest.mark.parametrize("suffix", (".geolog.json", ".geologpkg"))
def test_two_wells_persist_separate_marks_and_preserve_las_sources(tmp_path, suffix):
    session = _session()
    samples = {
        dataset_id: (well.datasets[dataset_id].depth.copy(),
                     well.datasets[dataset_id].curve_by_mnemonic("TG").values.copy())
        for well in session.project.wells.values()
        for dataset_id in well.datasets
    }
    session.report_compositions["dataset-a"] = ensure_report_composition_id(
        InterpretationReportComposition(preview_marks=(_mark("Well A"),)), "dataset-a",
    )
    session.report_compositions["dataset-b"] = ensure_report_composition_id(
        InterpretationReportComposition(preview_marks=(_mark("Well B", 1),)), "dataset-b",
    )
    path = tmp_path / f"preview-persistence{suffix}"
    ProjectController(session=session).save_project(path)
    loaded = ProjectController().open_project(path)
    assert not loaded.dirty
    assert loaded.report_compositions["dataset-a"].preview_marks == (_mark("Well A"),)
    assert loaded.report_compositions["dataset-b"].preview_marks == (_mark("Well B", 1),)
    for well in loaded.project.wells.values():
        for dataset_id, ds in well.datasets.items():
            original_depth, original_values = samples[dataset_id]
            np.testing.assert_array_equal(ds.depth, original_depth)
            np.testing.assert_array_equal(ds.curve_by_mnemonic("TG").values, original_values)


@pytest.mark.parametrize("language", list(AppLanguage))
def test_preview_dialog_commit_reopen_undo_and_redo(qapp, tmp_path, monkeypatch, language):
    session = _session()
    pdf = tmp_path / "proof.pdf"
    with fitz.open() as document:
        document.new_page()
        document.save(pdf)
    changes = []

    def commit(marks: tuple[PreviewMark, ...]) -> None:
        changes.append(marks)
        previous = session.report_compositions.get(
            "dataset-a", InterpretationReportComposition(),
        )
        session.report_compositions["dataset-a"] = ensure_report_composition_id(
            replace(previous, preview_marks=marks), "dataset-a",
        )
        session.dirty = True

    def open_dialog() -> FullReportPreviewDialog:
        existing = session.report_compositions.get("dataset-a", InterpretationReportComposition())
        return FullReportPreviewDialog(
            pdf, language=language, refresh_document=lambda: None,
            edit_annotations=lambda: None, export_document=lambda target: None,
            initial_marks=existing.preview_marks, on_marks_changed=commit,
        )

    dialog = open_dialog()
    try:
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("Шлам: аргиллит", True))
        dialog.mark_tool.setCurrentIndex(dialog.mark_tool.findData(PreviewMarkKind.TEXT))
        assert dialog._page_pointer(0, 0.25, 0.45, phase="press")
        assert session.dirty
        assert len(changes) == 1
        assert session.report_compositions["dataset-a"].preview_marks == (
            _mark("Шлам: аргиллит"),)
    finally:
        dialog.close()

    reopened = open_dialog()
    try:
        assert reopened._mark_history.current.marks == (_mark("Шлам: аргиллит"),)
        reopened.mark_tool.setCurrentIndex(reopened.mark_tool.findData("remove"))
        assert reopened._page_pointer(0, 0.25, 0.45, phase="press")
        assert session.report_compositions["dataset-a"].preview_marks == ()
        reopened.mark_undo_button.click()
        assert session.report_compositions["dataset-a"].preview_marks == (
            _mark("Шлам: аргиллит"),)
        reopened.mark_redo_button.click()
        assert session.report_compositions["dataset-a"].preview_marks == ()
    finally:
        reopened.close()
        qapp.processEvents()


@pytest.mark.parametrize("invalid", [
    None,
    {"kind": "text"},
    [{"kind": "fake", "page": 0, "x": 0.2, "y": 0.2, "text": "x", "points": []}],
    [{"kind": "text", "page": True, "x": 0.2, "y": 0.2, "text": "x", "points": []}],
    [{"kind": "text", "page": 0, "x": 1.2, "y": 0.2, "text": "x", "points": []}],
    [{"kind": "text", "page": 0, "x": 0.2, "y": 0.2, "text": "x", "points": [],
      "unexpected": 1}],
])
def test_codec_rejects_invalid_mark_payload(invalid):
    with pytest.raises((TypeError, ValueError)):
        preview_marks_from_list(invalid)


def test_persisted_mark_decoder_rejects_unknown_fields(tmp_path):
    session = _session()
    target = tmp_path / "invalid-preview.geolog.json"
    save_project(
        session.project, target,
        report_compositions={
            "dataset-a": InterpretationReportComposition(preview_marks=(_mark("x"),)),
        },
    )
    document = json.loads(target.read_text(encoding="utf-8"))
    document["report_compositions"]["dataset-a"]["preview_marks"][0]["unknown"] = True
    target.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ProjectFormatError, match="report composition"):
        load_project_document(target)


def test_bounded_preview_mark_codec_and_duplicate_stroke_round_trip():
    stroke = PreviewMark(
        PreviewMarkKind.FREEHAND, 1, 0.1, 0.2,
        points=((0.1, 0.2), (0.4, 0.5), (0.4, 0.5)),
    )
    assert preview_marks_from_list(preview_marks_to_list((stroke,))) == (stroke,)
    with pytest.raises(ValueError):
        preview_marks_to_list((_mark("too many"),) * 513)
    with pytest.raises(ValueError):
        preview_marks_from_list(preview_marks_to_list((stroke,)) * 513)
