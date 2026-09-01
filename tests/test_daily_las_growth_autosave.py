from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.storage.project_file_safety import (
    ProjectChangedExternallyError,
    SaveMode,
)
from geoworkbench.ui.main_window import MainWindow


def _session() -> ProjectSession:
    dataset = Dataset(
        "dataset-1",
        "Daily dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray([100.0, 101.0]),
    )
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    return ProjectSession(
        project=Project("project-1", "Daily project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
    )


class _ProjectController:
    def __init__(self, session: ProjectSession, project_path: Path | None) -> None:
        self.session = session
        self.project_path = project_path
        self.last_save_result: object | None = None
        self.save_calls: list[tuple[Path | None, SaveMode, bool]] = []
        self.preflight_error: Exception | None = None
        self.save_error: Exception | None = None
        self.recovery_records: tuple[object, ...] = ()
        self.restore_calls: list[tuple[object, Path]] = []

    def assert_project_storage_current(self) -> None:
        if self.preflight_error is not None:
            raise self.preflight_error

    def select_existing_dataset(self, dataset_id: str) -> Dataset:
        self.session.current_dataset_id = dataset_id
        dataset = self.session.current_dataset
        assert dataset is not None
        return dataset

    def save_project(
        self,
        target: Path | None = None,
        *,
        mode: SaveMode = SaveMode.EXPLICIT,
        allow_existing_target: bool = False,
    ) -> Path:
        self.save_calls.append((target, mode, allow_existing_target))
        if self.save_error is not None:
            raise self.save_error
        if target is not None:
            self.project_path = target
        assert self.project_path is not None
        self.session.dirty = False
        self.last_save_result = SimpleNamespace(
            backup=SimpleNamespace(
                backup_path=self.project_path.parent / ".geolog-backups" / "previous.geologpkg"
            ),
            warnings=(),
        )
        return self.project_path

    def recovery_candidates(self) -> tuple[object, ...]:
        return self.recovery_records

    def restore_backup_as_copy(self, record: object, target: Path) -> object:
        self.restore_calls.append((record, target))
        return object()


class _DailyController:
    def __init__(self, session: ProjectSession, *, material: bool) -> None:
        self.session = session
        self.material = material
        self.apply_calls = 0
        self.reset_calls = 0

    def apply(self, plan: object) -> object:
        self.apply_calls += 1
        if self.material:
            self.session.dirty = True
            record: object | None = object()
        else:
            record = None
        return SimpleNamespace(
            record=record,
            plan=SimpleNamespace(rows_added=2 if self.material else 0, rows_skipped=1),
        )

    def reset_state(self) -> None:
        self.reset_calls += 1


def _prepare_window(
    monkeypatch,
    *,
    project_path: Path | None,
    material: bool,
) -> tuple[MainWindow, _ProjectController, _DailyController, list[str], list[str]]:
    window = MainWindow(language=AppLanguage.EN)
    session = _session()
    project = _ProjectController(session, project_path)
    daily = _DailyController(session, material=material)
    window.project_controller = project  # type: ignore[assignment]
    window.daily_las_growth_controller = daily  # type: ignore[assignment]
    plan = SimpleNamespace(target_dataset_id="dataset-1")

    class _AcceptedDialog:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.plan = plan

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "geoworkbench.ui.main_window.DailyLasGrowthDialog",
        _AcceptedDialog,
    )
    refreshes: list[str] = []
    logs: list[str] = []
    monkeypatch.setattr(window, "_refresh_after_daily_las_growth", lambda: refreshes.append("yes"))
    monkeypatch.setattr(window, "_update_title", lambda: None)
    monkeypatch.setattr(window, "_log", logs.append)
    monkeypatch.setattr(window, "_acknowledge_background_project_save", lambda: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *_args, **_kwargs: QMessageBox.StandardButton.Ok)
    return window, project, daily, refreshes, logs


def test_material_daily_append_autosaves_package_and_reports_backup(
    qapp,
    monkeypatch,
    tmp_path: Path,
) -> None:
    window, project, daily, refreshes, logs = _prepare_window(
        monkeypatch,
        project_path=tmp_path / "well.geologpkg",
        material=True,
    )

    window.show_daily_las_growth()

    assert daily.apply_calls == 1
    assert project.save_calls == [(None, SaveMode.MATERIAL_AUTOSAVE, False)]
    assert project.session.dirty is False
    assert refreshes == ["yes"]
    assert "saved automatically" in window.statusBar().currentMessage()
    assert ".geolog-backups" in logs[-1]
    window.hide()


def test_duplicate_daily_las_is_noop_without_save_or_backup(
    qapp,
    monkeypatch,
    tmp_path: Path,
) -> None:
    window, project, daily, refreshes, _logs = _prepare_window(
        monkeypatch,
        project_path=tmp_path / "well.geologpkg",
        material=False,
    )

    window.show_daily_las_growth()

    assert daily.apply_calls == 1
    assert project.save_calls == []
    assert project.session.dirty is False
    assert refreshes == ["yes"]
    assert "No new rows" in window.statusBar().currentMessage()
    window.hide()


def test_preflight_external_conflict_does_not_apply_or_mutate(
    qapp,
    monkeypatch,
    tmp_path: Path,
) -> None:
    window, project, daily, refreshes, _logs = _prepare_window(
        monkeypatch,
        project_path=tmp_path / "well.geologpkg",
        material=True,
    )
    project.preflight_error = ProjectChangedExternallyError("external")
    critical: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda _parent, _title, message, *_args, **_kwargs: critical.append(message),
    )

    window.show_daily_las_growth()

    assert daily.apply_calls == 0
    assert daily.reset_calls == 1
    assert project.save_calls == []
    assert project.session.dirty is False
    assert refreshes == []
    assert "changed outside this session" in critical[-1]
    window.hide()


def test_post_append_save_conflict_keeps_in_memory_rows_dirty(
    qapp,
    monkeypatch,
    tmp_path: Path,
) -> None:
    window, project, daily, refreshes, _logs = _prepare_window(
        monkeypatch,
        project_path=tmp_path / "well.geologpkg",
        material=True,
    )
    project.save_error = ProjectChangedExternallyError("raced")
    critical: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda _parent, _title, message, *_args, **_kwargs: critical.append(message),
    )

    window.show_daily_las_growth()

    assert daily.apply_calls == 1
    assert project.save_calls == [(None, SaveMode.MATERIAL_AUTOSAVE, False)]
    assert project.session.dirty is True
    assert refreshes == ["yes"]
    assert "appended in memory" in critical[-1]
    assert "changed outside this session" in critical[-1]
    window.hide()


def test_cancelled_package_target_leaves_dataset_unchanged(
    qapp,
    monkeypatch,
) -> None:
    window, project, daily, refreshes, _logs = _prepare_window(
        monkeypatch,
        project_path=None,
        material=True,
    )
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_args, **_kwargs: ("", ""))

    window.show_daily_las_growth()

    assert daily.apply_calls == 0
    assert daily.reset_calls == 1
    assert project.save_calls == []
    assert project.session.dirty is False
    assert refreshes == []
    window.hide()


def test_legacy_project_is_saved_as_package_before_material_append(
    qapp,
    monkeypatch,
    tmp_path: Path,
) -> None:
    window, project, daily, refreshes, _logs = _prepare_window(
        monkeypatch,
        project_path=tmp_path / "legacy.geolog.json",
        material=True,
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(tmp_path / "working"), ""),
    )

    window.show_daily_las_growth()

    assert daily.apply_calls == 1
    assert project.save_calls == [
        (tmp_path / "working.geologpkg", SaveMode.EXPLICIT, True),
        (None, SaveMode.MATERIAL_AUTOSAVE, False),
    ]
    assert project.project_path == tmp_path / "working.geologpkg"
    assert project.session.dirty is False
    assert refreshes == ["yes"]
    window.hide()


def test_recovery_action_restores_selected_revision_only_as_new_copy(
    qapp,
    monkeypatch,
    tmp_path: Path,
) -> None:
    window, project, _daily, _refreshes, _logs = _prepare_window(
        monkeypatch,
        project_path=tmp_path / "well.geologpkg",
        material=False,
    )
    record = SimpleNamespace(
        save_revision=4,
        created_at="2026-09-01T08:00:00+00:00",
        backup_path=tmp_path / ".geolog-backups" / "revision-4.geologpkg",
    )
    project.recovery_records = (record,)
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        lambda _parent, _title, _prompt, items, *_args, **_kwargs: (items[0], True),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(tmp_path / "recovered"), ""),
    )
    messages: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, _title, message, *_args, **_kwargs: messages.append(message),
    )

    window.restore_project_backup()

    assert project.restore_calls == [(record, tmp_path / "recovered.geologpkg")]
    assert project.project_path == tmp_path / "well.geologpkg"
    assert "active project was not switched" in messages[-1]
    window.hide()
