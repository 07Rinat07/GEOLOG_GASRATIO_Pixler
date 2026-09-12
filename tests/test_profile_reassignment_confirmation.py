from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtWidgets import QDialogButtonBox, QMessageBox

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.domain.rock_code_profiles import RockCodeSourceBindingRecord
from geoworkbench.project.daily_las_growth_controller import DailyLasGrowthController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.daily_las_growth import DailyLasGrowthError
from geoworkbench.services.persisted_rock_code_profile_assignment import (
    RockCodeProfileReassignmentRequired,
    assign_persisted_rock_code_profile,
)
from geoworkbench.services.rock_code_dictionary import RockCodeDictionary
from geoworkbench.services.well_update_plan import analyze_well_numerical_update
from geoworkbench.ui.daily_las_growth_dialog import DailyLasGrowthDialog


def _dataset(dataset_id: str) -> Dataset:
    return Dataset(
        dataset_id,
        dataset_id,
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray([100.0, 101.0], dtype=float),
    )


def _session() -> tuple[ProjectSession, Dataset]:
    target = _dataset("target")
    well = Well("well-1", "Well", datasets={target.dataset_id: target})
    session = ProjectSession(
        project=Project("project-1", "Daily project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=target.dataset_id,
    )
    return session, target


def _write_source(path: Path) -> str:
    path.write_bytes(b"daily-las-source")
    return sha256(path.read_bytes()).hexdigest()


def _write_profile(path: Path, dictionary: RockCodeDictionary) -> None:
    path.write_text(dictionary.to_json(), encoding="utf-8")


def _patch_import(monkeypatch, *, source_sha256: str, source: Dataset) -> None:
    imported = SimpleNamespace(
        dataset=source,
        report=SimpleNamespace(source=SimpleNamespace(sha256=source_sha256)),
        source_document=SimpleNamespace(size_bytes=len(b"daily-las-source")),
    )
    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller.import_las_with_report",
        lambda *_args, **_kwargs: imported,
    )


def _patch_analysis(monkeypatch, target: Dataset) -> SimpleNamespace:
    numerical_plan = SimpleNamespace(
        target_dataset_id=target.dataset_id,
        start_value=100.0,
        stop_value=101.0,
    )
    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller.analyze_well_numerical_update",
        lambda *_args, **_kwargs: numerical_plan,
    )

    def _analyze_geology(
        actual_session: ProjectSession,
        _target: Dataset,
        _source: Dataset,
        *,
        source_sha256: str,
        **_kwargs,
    ) -> SimpleNamespace:
        binding = actual_session.rock_code_source_bindings[source_sha256]
        return SimpleNamespace(profile_sha256=binding.profile_sha256)

    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller."
        "analyze_persisted_well_geology_update",
        _analyze_geology,
    )
    return numerical_plan


def test_controller_requires_explicit_reassignment_preview_and_commits_exact_revision(
    monkeypatch,
    tmp_path: Path,
) -> None:
    session, target = _session()
    source = _dataset("source")
    source_path = tmp_path / "daily.las"
    source_sha256 = _write_source(source_path)
    old_profile = RockCodeDictionary(name="Profile v1", source="Supplier A", entries=())
    new_profile = RockCodeDictionary(name="Profile v2", source="Supplier A", entries=())
    profile_path = tmp_path / "supplier-profile.json"
    _write_profile(profile_path, new_profile)

    old_assignment = assign_persisted_rock_code_profile(
        session,
        source_sha256=source_sha256,
        supplier_name=old_profile.source,
        dictionary=old_profile,
    )
    session.dirty = False
    _patch_import(monkeypatch, source_sha256=source_sha256, source=source)
    numerical_plan = _patch_analysis(monkeypatch, target)
    controller = DailyLasGrowthController(session)

    with pytest.raises(RockCodeProfileReassignmentRequired) as exc_info:
        controller.analyze_numerical(
            source_path,
            target.dataset_id,
            geology_profile_path=profile_path,
        )
    assert exc_info.value.current_binding == old_assignment.binding
    assert session.rock_code_source_bindings[source_sha256] == old_assignment.binding
    assert session.dirty is False

    result = controller.analyze_numerical(
        source_path,
        target.dataset_id,
        geology_profile_path=profile_path,
        allow_profile_reassignment=True,
    )
    geology_plan = controller.geology_plan
    assert result is numerical_plan
    assert geology_plan is not None
    assert session.rock_code_source_bindings[source_sha256] == old_assignment.binding
    assert session.dirty is False

    expected_new_sha256 = sha256(new_profile.to_json().encode("utf-8")).hexdigest()

    def _prepare(
        actual_session: ProjectSession,
        *_args,
        source_sha256: str,
        **_kwargs,
    ) -> None:
        assert actual_session.rock_code_source_bindings[source_sha256].profile_sha256 == (
            expected_new_sha256
        )
        return None

    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller."
        "prepare_persisted_well_geology_update",
        _prepare,
    )
    outcome = SimpleNamespace(record=None, geology_record=None)
    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller.apply_well_numerical_update",
        lambda *_args, **_kwargs: outcome,
    )

    assert controller.apply_numerical(numerical_plan, geology_plan=geology_plan) is outcome
    binding = session.rock_code_source_bindings[source_sha256]
    assert binding.profile_sha256 == expected_new_sha256
    assert old_assignment.profile.profile_sha256 in session.rock_code_profiles
    assert expected_new_sha256 in session.rock_code_profiles
    assert session.dirty is True


def test_authorized_reassignment_is_rejected_if_binding_changes_after_preview(
    monkeypatch,
    tmp_path: Path,
) -> None:
    session, target = _session()
    source = _dataset("source")
    source_path = tmp_path / "daily.las"
    source_sha256 = _write_source(source_path)
    old_profile = RockCodeDictionary(name="Profile v1", source="Supplier A", entries=())
    requested_profile = RockCodeDictionary(
        name="Profile v2", source="Supplier A", entries=()
    )
    third_profile = RockCodeDictionary(name="Profile v3", source="Supplier A", entries=())
    profile_path = tmp_path / "supplier-profile.json"
    _write_profile(profile_path, requested_profile)

    assign_persisted_rock_code_profile(
        session,
        source_sha256=source_sha256,
        supplier_name=old_profile.source,
        dictionary=old_profile,
    )
    _patch_import(monkeypatch, source_sha256=source_sha256, source=source)
    numerical_plan = _patch_analysis(monkeypatch, target)
    controller = DailyLasGrowthController(session)
    controller.analyze_numerical(
        source_path,
        target.dataset_id,
        geology_profile_path=profile_path,
        allow_profile_reassignment=True,
    )
    geology_plan = controller.geology_plan
    assert geology_plan is not None

    assign_persisted_rock_code_profile(
        session,
        source_sha256=source_sha256,
        supplier_name=third_profile.source,
        dictionary=third_profile,
        allow_reassignment=True,
    )
    monkeypatch.setattr(
        "geoworkbench.project.daily_las_growth_controller.apply_well_numerical_update",
        lambda *_args, **_kwargs: pytest.fail("stale authorization must not apply"),
    )

    with pytest.raises(
        DailyLasGrowthError,
        match="Привязка источника к профилю пород изменилась",
    ):
        controller.apply_numerical(numerical_plan, geology_plan=geology_plan)


def test_dialog_retries_preview_only_after_explicit_profile_reassignment_confirmation(
    qapp,
    monkeypatch,
    tmp_path: Path,
) -> None:
    session, target = _session()
    controller = DailyLasGrowthController(session)
    dialog = DailyLasGrowthDialog(controller)
    source_path = tmp_path / "daily.las"
    source_path.write_bytes(b"preview")
    source = _dataset("source")
    plan = analyze_well_numerical_update(
        target,
        source,
        source_name=source_path.name,
        source_sha256="a" * 64,
    )
    current = RockCodeSourceBindingRecord(
        source_sha256="a" * 64,
        supplier_name="Supplier A",
        profile_sha256="b" * 64,
    )
    requested = RockCodeSourceBindingRecord(
        source_sha256="a" * 64,
        supplier_name="Supplier B",
        profile_sha256="c" * 64,
    )
    conflict = RockCodeProfileReassignmentRequired(current, requested)
    calls: list[dict[str, object]] = []

    def _analyze_numerical(*_args, **kwargs):
        calls.append(dict(kwargs))
        if len(calls) == 1:
            raise conflict
        return plan

    monkeypatch.setattr(controller, "analyze_numerical", _analyze_numerical)
    question_calls: list[str] = []

    def _question(_parent, _title, message, *_args):
        question_calls.append(message)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", _question)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args: pytest.fail("confirmed reassignment should not warn"),
    )

    dialog.file_input.setText(str(source_path))
    dialog.numerical_mode.setChecked(True)
    dialog.geology_enabled.setChecked(True)
    dialog.profile_input.setText(str(tmp_path / "profile.json"))
    dialog._analyze()

    assert dialog.plan is plan
    assert len(calls) == 2
    assert "allow_profile_reassignment" not in calls[0]
    assert calls[1]["allow_profile_reassignment"] is True
    assert question_calls
    assert current.supplier_name in question_calls[0]
    assert current.profile_sha256 in question_calls[0]
    assert requested.supplier_name in question_calls[0]
    assert requested.profile_sha256 in question_calls[0]
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    dialog.close()


def test_dialog_declining_profile_reassignment_keeps_preview_invalid(
    qapp,
    monkeypatch,
    tmp_path: Path,
) -> None:
    session, _target = _session()
    controller = DailyLasGrowthController(session)
    dialog = DailyLasGrowthDialog(controller)
    source_path = tmp_path / "daily.las"
    source_path.write_bytes(b"preview")
    current = RockCodeSourceBindingRecord(
        source_sha256="a" * 64,
        supplier_name="Supplier A",
        profile_sha256="b" * 64,
    )
    requested = RockCodeSourceBindingRecord(
        source_sha256="a" * 64,
        supplier_name="Supplier B",
        profile_sha256="c" * 64,
    )
    conflict = RockCodeProfileReassignmentRequired(current, requested)
    calls = 0

    def _analyze_numerical(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise conflict

    monkeypatch.setattr(controller, "analyze_numerical", _analyze_numerical)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args: QMessageBox.StandardButton.No,
    )

    dialog.file_input.setText(str(source_path))
    dialog.numerical_mode.setChecked(True)
    dialog.geology_enabled.setChecked(True)
    dialog.profile_input.setText(str(tmp_path / "profile.json"))
    dialog._analyze()

    assert calls == 1
    assert dialog.plan is None
    assert "не изменён" in dialog.preview.toPlainText()
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    dialog.close()
