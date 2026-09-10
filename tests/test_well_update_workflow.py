from copy import deepcopy
import json

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox

from test_daily_las_growth_dialog import _controller, FIXTURES
from geoworkbench.services.daily_las_growth import DailyLasGrowthError, dataset_append_state_sha256
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import ProjectDocument, ProjectFormatError, project_document_from_dict
from geoworkbench.storage.project_migrations import migrate_project_payload
from geoworkbench.ui.daily_las_growth_dialog import DailyLasGrowthDialog
from geoworkbench.services.localization import AppLanguage


def _source(tmp_path):
    path = tmp_path / "daily.las"
    path.write_bytes((FIXTURES / "02_daily_append.las").read_bytes().replace(b"1002.0 14.0", b"1002.0 99.0"))
    return path


def test_controller_package_roundtrip_preserves_audit_original_las_and_id(tmp_path):
    controller = _controller()
    target = controller.session.current_dataset
    original_docs = dict(controller.session.source_documents)
    plan = controller.analyze_numerical(_source(tmp_path), target.dataset_id)
    selected = tuple(c for c in plan.changes if c.target_row is not None)
    outcome = controller.apply_numerical(plan, append_rows=True, selected_changes=selected)
    assert target.curve_by_mnemonic("ROP").values[4] == 99
    assert len(target.depth) == 9
    assert controller.session.dirty
    assert len(target.source_revisions) == 2
    assert target.source_revisions[0].rows_added == 5
    for doc in original_docs.values():
        assert doc in controller.session.source_documents.values()
    repository = PackageProjectRepository()
    path = tmp_path / "well.geologpkg"
    repository.save(ProjectDocument(controller.session.project,
                                   source_documents=controller.session.source_documents), path)
    loaded = repository.load(path)
    restored = next(iter(loaded.project.wells.values())).datasets[target.dataset_id]
    assert restored.numerical_update_history == [outcome.record]
    assert restored.source_revisions == target.source_revisions
    assert loaded.source_documents == controller.session.source_documents
    np.testing.assert_equal(restored.curve_by_mnemonic("ROP").values, target.curve_by_mnemonic("ROP").values)
    fresh = controller.analyze_numerical(_source(tmp_path), target.dataset_id)
    assert controller.apply_numerical(fresh, append_rows=True).record is None


@pytest.mark.parametrize("failure", ["file_changed", "post_apply"])
def test_controller_failure_rolls_back_and_consumes_preview(tmp_path, monkeypatch, failure):
    controller = _controller()
    target = controller.session.current_dataset
    source = _source(tmp_path)
    plan = controller.analyze_numerical(source, target.dataset_id)
    before = dataset_append_state_sha256(target)
    documents = dict(controller.session.source_documents)
    dirty = controller.session.dirty
    if failure == "file_changed":
        source.write_bytes(source.read_bytes() + b"\n")
    else:
        preserve = controller._preserve_initial_source
        def fail(*args, **kwargs):
            preserve(*args, **kwargs)
            raise OSError("injected artifact failure")
        monkeypatch.setattr(controller, "_preserve_initial_source", fail)
    with pytest.raises((DailyLasGrowthError, OSError)):
        controller.apply_numerical(plan, append_rows=True)
    assert dataset_append_state_sha256(target) == before
    assert controller.session.source_documents == documents
    assert controller.session.dirty == dirty
    with pytest.raises(DailyLasGrowthError, match="повторно"):
        controller.apply_numerical(plan)


@pytest.mark.parametrize("language", list(AppLanguage))
def test_dialog_selection_is_explicit_and_resets_on_analysis_or_cancel(qapp, tmp_path, language):
    controller = _controller()
    dialog = DailyLasGrowthDialog(controller, language=language)
    dialog.numerical_mode.setChecked(True)
    dialog.file_input.setText(str(_source(tmp_path)))
    dialog._analyze()
    assert dialog.change_table.rowCount() == 1
    assert not dialog.selected_numerical_changes()
    assert not dialog.append_rows.isChecked()
    dialog.change_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    assert len(dialog.selected_numerical_changes()) == 1
    dialog.append_rows.setChecked(True)
    dialog._analyze()
    assert not dialog.selected_numerical_changes()
    assert not dialog.append_rows.isChecked()
    dialog.reject()
    assert dialog.plan is None
    assert controller._numerical_plan is None
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()


def test_v25_migration_is_nonmutating_and_preserves_legacy_fields():
    raw = {"format_version": 25, "project": {"wells": {"w": {"datasets": {
        "d": {"dataset_id": "d", "headers": {"WELL": "old"}, "depth": [1, 2]},
    }}}}}
    original = deepcopy(raw)
    migrated = migrate_project_payload(raw, 26)
    assert migrated["format_version"] == 26
    dataset = migrated["project"]["wells"]["w"]["datasets"]["d"]
    assert dataset.pop("numerical_update_history") == []
    assert dataset == raw["project"]["wells"]["w"]["datasets"]["d"]
    assert raw == original


@pytest.mark.parametrize("damage", ["count", "hash", "nan", "unknown", "duplicate", "limit"])
def test_codec_rejects_malformed_update_audit(tmp_path, damage):
    from dataclasses import asdict
    controller = _controller()
    target = controller.session.current_dataset
    plan = controller.analyze_numerical(_source(tmp_path), target.dataset_id)
    controller.apply_numerical(plan, selected_changes=(plan.changes[0],))
    raw = asdict(controller.session.project)
    # Match the decoded JSON representation (including enum strings / lists).
    raw = json.loads(json.dumps(raw, default=lambda v: v.tolist() if isinstance(v, np.ndarray) else str(v)))
    payload = {"format_version": 26, "project": raw, "tablet_layouts": {}, "tablet_presets": {}}
    assert project_document_from_dict(payload).project.wells
    record = raw["wells"][controller.session.current_well_id]["datasets"][target.dataset_id]["numerical_update_history"][0]
    if damage == "count":
        record["rows_added"] = True
    elif damage == "hash":
        record["source_sha256"] = "bad"
    elif damage == "nan":
        record["changes"][0]["after"] = float("nan")
    elif damage == "unknown":
        record["changes"][0]["kind"] = "clear"
    elif damage == "duplicate":
        record["changes"] *= 2
    else:
        record["changes"] *= 10001
    with pytest.raises(ProjectFormatError, match="числов"):
        project_document_from_dict(payload)


@pytest.mark.parametrize("scenario", ["save", "no_selection", "disk_full", "external", "cancel"])
def test_main_window_numerical_save_gate(qapp, monkeypatch, tmp_path, scenario):
    from types import SimpleNamespace
    from PySide6.QtWidgets import QDialog, QMessageBox
    from test_daily_las_growth_autosave import _prepare_window
    from geoworkbench.storage.project_file_safety import ProjectChangedExternallyError, SaveMode

    window, project, _, _, logs = _prepare_window(
        monkeypatch, project_path=tmp_path / "well.geologpkg", material=True,
    )
    controller = _controller()
    project.session = controller.session
    window.daily_las_growth_controller = controller
    controller.session.dirty = False
    target = controller.session.current_dataset
    plan = controller.analyze_numerical(_source(tmp_path), target.dataset_id)
    before = dataset_append_state_sha256(target)
    class Accepted:
        def __init__(self, *args, **kwargs):
            self.plan = plan
            self.append_rows = SimpleNamespace(isChecked=lambda: False)
        def selected_numerical_changes(self):
            return () if scenario == "no_selection" else (plan.changes[0],)
        def exec(self):
            return QDialog.DialogCode.Accepted
    monkeypatch.setattr("geoworkbench.ui.main_window.DailyLasGrowthDialog", Accepted)
    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda _p, _t, msg: errors.append(msg))
    if scenario == "disk_full":
        project.save_error = OSError(28, "No space left on device")
    elif scenario == "external":
        project.preflight_error = ProjectChangedExternallyError("changed")
    elif scenario == "cancel":
        monkeypatch.setattr(window, "_ensure_daily_las_project_target", lambda: False)
    window.show_daily_las_growth()
    if scenario in {"no_selection", "external", "cancel"}:
        assert dataset_append_state_sha256(target) == before
        assert not project.save_calls
        assert not controller.session.dirty
    else:
        assert target.curve_by_mnemonic("ROP").values[4] == 99
        assert project.save_calls == [(None, SaveMode.MATERIAL_AUTOSAVE, False)]
        assert controller.session.dirty == (scenario == "disk_full")
        if scenario == "disk_full":
            assert "not written" in errors[-1]
            assert not any("Numerical update saved" in line for line in logs)
        else:
            assert "Numerical update saved: 0 new rows, 1 selected cells" in logs[-1]
            assert ".geolog-backups" in logs[-1]
    window.hide()


def test_partial_numerical_update_does_not_mark_unselected_suffix_imported(tmp_path):
    controller = _controller()
    target = controller.session.current_dataset
    path = _source(tmp_path)
    plan = controller.analyze_numerical(path, target.dataset_id)
    controller.apply_numerical(plan, selected_changes=(plan.changes[0],))
    assert len(target.depth) == 5
    strict = controller.analyze(path, target.dataset_id)
    assert strict.rows_added == 4
    assert not strict.duplicate_source
    controller.apply(strict)
    assert len(target.depth) == 9
    assert target.curve_by_mnemonic("ROP").values[4] == 99
