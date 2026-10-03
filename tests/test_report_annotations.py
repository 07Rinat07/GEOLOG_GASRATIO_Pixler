from __future__ import annotations

from dataclasses import replace
import json

import numpy as np
import pytest

from geoworkbench.domain.annotation_style import AnnotationStyle as DomainAnnotationStyle
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.domain.report_annotations import (
    ReportAnnotationAnchor,
    ReportAnnotationKind,
    ReportAnnotationRecord,
    normalize_report_track_key,
    report_annotation_scope_id,
)
from geoworkbench.domain.report_composition import (
    InterpretationReportComposition,
    ReportPageOrientation,
    stable_report_composition_id,
)
from geoworkbench.project.annotation_schema import AnnotationStyle
from geoworkbench.project.report_annotation_controller import ReportAnnotationController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.edit_history import CallbackCommand, CommandHistory
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import (
    PROJECT_FORMAT_VERSION,
    ProjectDocument,
    ProjectFormatError,
    load_project_document,
)


WELL_ID = "well-report-annotation"
DATASET_ID = "dataset-report-annotation"


def _project() -> Project:
    dataset = Dataset(
        DATASET_ID,
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray([1000.0, 1001.0, 1002.0], dtype=np.float64),
    )
    well = Well(WELL_ID, "Well", datasets={dataset.dataset_id: dataset})
    return Project("project-report-annotation", "Project", wells={well.well_id: well})


def _composition(*annotations: ReportAnnotationRecord) -> InterpretationReportComposition:
    return InterpretationReportComposition(
        composition_id=stable_report_composition_id(DATASET_ID),
        annotations=tuple(annotations),
    )


def _annotation(*, scope_id: str | None = None) -> ReportAnnotationRecord:
    composition_id = stable_report_composition_id(DATASET_ID)
    return ReportAnnotationRecord(
        annotation_id="rann-test",
        scope_id=scope_id or report_annotation_scope_id(WELL_ID, DATASET_ID, composition_id),
        kind=ReportAnnotationKind.CALLOUT,
        anchor=ReportAnnotationAnchor.DEPTH,
        text="Проверка",
        track_key="curve:TG",
        depth=1001.0,
        text_i18n={"ru": "Проверка", "en": "Check"},
    )


def _session() -> ProjectSession:
    return ProjectSession(
        project=_project(),
        current_well_id=WELL_ID,
        current_dataset_id=DATASET_ID,
    )


def test_tablet_annotation_import_keeps_shared_domain_style_identity() -> None:
    assert AnnotationStyle is DomainAnnotationStyle


def test_report_scope_and_logical_track_keys_are_explicit_and_tablet_independent() -> None:
    composition_id = stable_report_composition_id(DATASET_ID)

    scope = report_annotation_scope_id(WELL_ID, DATASET_ID, composition_id)

    assert scope == f"report:{WELL_ID}:{DATASET_ID}:{composition_id}"
    assert ":tablet:" not in scope
    assert normalize_report_track_key("geology:cuttings") == "geology:cuttings"
    assert normalize_report_track_key("geology:lba") == "geology:lba"
    assert normalize_report_track_key("depth:left") == "depth:left"
    assert normalize_report_track_key("curve:TG") == "curve:TG"
    with pytest.raises(ValueError, match="logical report-track key"):
        normalize_report_track_key("tablet:track-1")


def test_project_v37_round_trip_preserves_report_annotations(tmp_path) -> None:
    target = tmp_path / "annotations.geolog.json"
    annotation = _annotation()
    composition = _composition(annotation)

    save_project(
        _project(),
        target,
        report_compositions={DATASET_ID: composition},
    )
    loaded = load_project_document(target)

    assert PROJECT_FORMAT_VERSION == 37
    assert loaded.report_compositions[DATASET_ID] == composition


def test_existing_v37_without_annotations_defaults_to_empty_snapshot(tmp_path) -> None:
    target = tmp_path / "legacy-v37-annotations.geolog.json"
    save_project(
        _project(),
        target,
        report_compositions={DATASET_ID: _composition(_annotation())},
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["report_compositions"][DATASET_ID].pop("annotations")
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded = load_project_document(target)

    assert loaded.report_compositions[DATASET_ID].annotations == ()


def test_save_and_load_reject_foreign_report_annotation_scope(tmp_path) -> None:
    foreign = _annotation(scope_id="report:other-well:other-dataset:rpt-foreign")
    target = tmp_path / "foreign-scope.geolog.json"

    with pytest.raises(ValueError, match="чужую область"):
        save_project(
            _project(),
            target,
            report_compositions={DATASET_ID: _composition(foreign)},
        )

    save_project(
        _project(),
        target,
        report_compositions={DATASET_ID: _composition(_annotation())},
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["report_compositions"][DATASET_ID]["annotations"][0]["scope_id"] = (
        "report:other-well:other-dataset:rpt-foreign"
    )
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ProjectFormatError, match="чужую область"):
        load_project_document(target)


def test_package_round_trip_preserves_report_annotation_snapshot(tmp_path) -> None:
    document = ProjectDocument(
        project=_project(),
        report_compositions={DATASET_ID: _composition(_annotation())},
    )
    target = tmp_path / "annotations.geologpkg"
    repository = PackageProjectRepository()

    repository.save(document, target)
    loaded = repository.load(target)

    assert loaded.report_compositions == document.report_compositions


def test_controller_uses_report_scope_and_shared_bounded_history_for_twenty_edits() -> None:
    session = _session()
    history = CommandHistory(max_commands=100)
    controller = ReportAnnotationController(session, shared_history=history)

    created = [
        controller.add(
            text=f"Callout {index}",
            depth=1000.0 + index / 100.0,
            track_key="curve:TG",
        )
        for index in range(20)
    ]

    assert len(controller.available()) == 20
    assert all(item.scope_id == controller.current_scope_id() for item in created)
    assert all(item.scope_id.startswith(f"report:{WELL_ID}:{DATASET_ID}:") for item in created)
    for _ in range(20):
        controller.undo()

    assert DATASET_ID not in session.report_compositions
    assert not controller.can_undo
    assert controller.can_redo

    for _ in range(20):
        controller.redo()

    assert tuple(item.annotation_id for item in controller.available()) == tuple(
        item.annotation_id for item in created
    )
    assert controller.can_undo
    assert not controller.can_redo


def test_controller_update_remove_and_conflict_guards_are_reversible() -> None:
    session = _session()
    history = CommandHistory()
    controller = ReportAnnotationController(session, shared_history=history)
    created = controller.add(text="Before", depth=1001.0, track_key="curve:TG")

    updated = controller.update(
        created.annotation_id,
        text="After",
        text_i18n={"ru": "После", "en": "After"},
        offset_x=42.0,
    )
    removed = controller.remove(created.annotation_id)

    assert updated.text == "After"
    assert removed == updated
    assert controller.available() == ()

    controller.undo()
    assert controller.get(created.annotation_id) == updated
    controller.undo()
    assert controller.get(created.annotation_id) == created
    controller.redo()
    assert controller.get(created.annotation_id) == updated


def test_cancel_checkpoint_restores_annotations_and_history_without_parallel_stack() -> None:
    session = _session()
    history = CommandHistory()
    controller = ReportAnnotationController(session, shared_history=history)
    first = controller.add(text="Saved", depth=1000.0, track_key="curve:TG")
    checkpoint = controller.checkpoint()

    controller.add(text="Draft", depth=1001.0, track_key="geology:cuttings")
    controller.update(first.annotation_id, text="Draft update")
    assert len(controller.available()) == 2

    controller.restore(checkpoint)

    assert controller.available() == (first,)
    assert history.next_undo is not None
    assert history.next_undo.history_domain == "report_annotation"
    assert not controller.can_redo


def test_cancel_checkpoint_restores_clean_dirty_state() -> None:
    session = _session()
    composition = _composition(_annotation())
    session.report_compositions[DATASET_ID] = composition
    session.dirty = False
    history = CommandHistory()
    controller = ReportAnnotationController(session, shared_history=history)
    checkpoint = controller.checkpoint()

    controller.add(text="Draft", depth=1001.5, track_key="curve:TG")
    assert session.dirty is True

    controller.restore(checkpoint)

    assert session.report_compositions[DATASET_ID] == composition
    assert session.dirty is False
    assert history.can_undo is False
    assert history.can_redo is False


def test_cancel_checkpoint_fails_closed_after_foreign_history_command() -> None:
    session = _session()
    history = CommandHistory()
    controller = ReportAnnotationController(session, shared_history=history)
    controller.add(text="Saved", depth=1000.0, track_key="curve:TG")
    checkpoint = controller.checkpoint()
    controller.add(text="Draft", depth=1001.0, track_key="curve:TG")
    history.execute(
        CallbackCommand(
            description="Foreign edit",
            history_domain="header",
            execute_action=lambda: None,
            undo_action=lambda: None,
        )
    )

    with pytest.raises(RuntimeError, match="другого домена"):
        controller.restore(checkpoint)


def test_report_annotation_presentation_conflict_blocks_undo() -> None:
    session = _session()
    history = CommandHistory()
    controller = ReportAnnotationController(session, shared_history=history)
    controller.add(text="Callout", depth=1000.0, track_key="curve:TG")
    current = session.report_compositions[DATASET_ID]
    session.report_compositions[DATASET_ID] = replace(
        current,
        orientation=ReportPageOrientation.LANDSCAPE,
    )

    with pytest.raises(RuntimeError, match="изменена вне истории report annotations"):
        controller.undo()
