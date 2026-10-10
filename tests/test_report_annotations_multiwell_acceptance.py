from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain, Project, Well,
)
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    HydrocarbonInterpretationPdfError,
    export_hydrocarbon_interpretation_pdf_with_passport,
)
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.report_annotation_controller import ReportAnnotationController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.hydrocarbon_interpretation import (
    build_hydrocarbon_interpretation_report,
)
from geoworkbench.tablet.models import TabletLayout


PAIRS = (
    ("well-a", "dataset-a", 1000.0),
    ("well-b", "dataset-b", 2000.0),
)


def _two_well_session() -> ProjectSession:
    wells: dict[str, Well] = {}
    for well_id, dataset_id, first_depth in PAIRS:
        dataset = Dataset(
            dataset_id, f"GTI {well_id}", DatasetKind.GTI, DepthDomain.MD,
            np.array([first_depth, first_depth + 1.0, first_depth + 2.0]),
        )
        curve = CurveData(
            CurveMetadata(
                f"curve-{dataset_id}", "C1", "C1", "%", "Methane",
                dataset_id, provenance="source",
            ),
            np.array([0.1, 0.2, 0.3], dtype=np.float64)
            + (1.0 if well_id == "well-b" else 0.0),
        )
        dataset.curves[curve.metadata.curve_id] = curve
        wells[well_id] = Well(well_id, f"Well {well_id}", {dataset_id: dataset})
    project = Project("multiwell-annotation-acceptance", "Test project", wells=wells)
    return ProjectSession(project, PAIRS[0][0], PAIRS[0][1])


def _select(session: ProjectSession, well_id: str, dataset_id: str) -> None:
    session.current_well_id = well_id
    session.current_dataset_id = dataset_id


@pytest.mark.parametrize("suffix", (".geolog.json", ".geologpkg"))
def test_two_wells_keep_independent_annotations_after_real_save_reopen(
    tmp_path: Path, suffix: str,
) -> None:
    session = _two_well_session()
    editor = ReportAnnotationController(session)
    before_source = {
        dataset_id: (
            np.copy(session.project.wells[well_id].datasets[dataset_id].depth),
            np.copy(
                session.project.wells[well_id].datasets[dataset_id]
                .curves[f"curve-{dataset_id}"].values
            ),
        )
        for well_id, dataset_id, _ in PAIRS
    }
    saved = {}
    for well_id, dataset_id, first_depth in PAIRS:
        _select(session, well_id, dataset_id)
        annotation = editor.add(
            text=f"Depth note {well_id}", depth=first_depth + 1.0,
            track_key="curve:C1",
            text_i18n={"ru": f"Скважина {well_id}", "en": f"Well {well_id}"},
        )
        saved[dataset_id] = annotation
        assert editor.available() == (annotation,)
        assert editor.current_scope_id() == annotation.scope_id
        assert annotation.scope_id.startswith(f"report:{well_id}:{dataset_id}:")
    assert saved["dataset-a"].scope_id != saved["dataset-b"].scope_id

    # Changing tablet layouts must not alter the report annotation owner.
    _select(session, "well-a", "dataset-a")
    original_scope = editor.current_scope_id()
    session.tablet_layouts["dataset-a"] = TabletLayout(
        annotation_scope_id="tablet:first-layout",
    )
    assert editor.current_scope_id() == original_scope
    session.tablet_layouts["dataset-a"] = TabletLayout(
        annotation_scope_id="tablet:second-layout",
    )
    assert editor.current_scope_id() == original_scope
    assert editor.available() == (saved["dataset-a"],)

    target = tmp_path / f"two-wells{suffix}"
    ProjectController(session=session).save_project(target)
    reopened = ProjectController().open_project(target)
    assert not reopened.dirty
    check = ReportAnnotationController(reopened)
    for well_id, dataset_id, first_depth in PAIRS:
        _select(reopened, well_id, dataset_id)
        assert check.current_scope_id() == saved[dataset_id].scope_id
        assert check.available() == (saved[dataset_id],)
        assert check.available()[0].depth == first_depth + 1.0
        dataset = reopened.current_dataset
        assert dataset is not None
        expected_depth, expected_values = before_source[dataset_id]
        np.testing.assert_array_equal(dataset.depth, expected_depth)
        assert list(dataset.curves) == [f"curve-{dataset_id}"]
        source_curve = dataset.curves[f"curve-{dataset_id}"]
        np.testing.assert_array_equal(source_curve.values, expected_values)
        assert source_curve.metadata.provenance == "source"

    # A note from well A must not be obtainable through well B's controller.
    _select(reopened, "well-b", "dataset-b")
    with pytest.raises(KeyError):
        check.get(saved["dataset-a"].annotation_id)


def test_signed_pdf_export_rejects_other_wells_annotation_but_accepts_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _two_well_session()
    editor = ReportAnnotationController(session)
    _select(session, "well-a", "dataset-a")
    note_a = editor.add(text="A note", depth=1001.0, track_key="curve:C1")
    _select(session, "well-b", "dataset-b")
    note_b = editor.add(text="B note", depth=2001.0, track_key="curve:C1")
    assert note_a.scope_id != note_b.scope_id
    report_b = build_hydrocarbon_interpretation_report(session)

    outputs = []
    def capture_transaction(output, producer, passport, *, overwrite=False):
        outputs.append((Path(output), passport))
        return SimpleNamespace(primary_path=Path(output))

    monkeypatch.setattr(
        "geoworkbench.printing.hydrocarbon_interpretation_report."
        "execute_report_output_transaction",
        capture_transaction,
    )
    foreign_target = tmp_path / "foreign.pdf"
    with pytest.raises(HydrocarbonInterpretationPdfError, match="другой скважине"):
        export_hydrocarbon_interpretation_pdf_with_passport(
            session, report_b, foreign_target, include_chart=True,
            annotations=(note_a,),
        )
    assert outputs == []
    assert not foreign_target.exists()
    assert not (tmp_path / "foreign.pdf.passport.json").exists()

    output = export_hydrocarbon_interpretation_pdf_with_passport(
        session, report_b, tmp_path / "own.pdf", include_chart=True,
        annotations=(note_b,),
    )
    assert output.primary_path == tmp_path / "own.pdf"
    assert len(outputs) == 1
    assert dict(outputs[0][1].render.options)["report_annotations"] == "1"
    assert editor.available() == (note_b,)
