import numpy as np
import pytest
from PySide6.QtCore import QSettings

from geoworkbench.acquisition.wits0_reliability import Wits0WorkspaceSettings, Wits0WorkspaceState
from geoworkbench.domain.models import Project, Well
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.wits0_acquisition import Wits0AcquisitionRuntime
import geoworkbench.ui.wits0_capture_dialog as capture
from test_wits0_acquisition import _frame, _time_commit


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("suffix", [".geolog.json", ".geologpkg"])
def test_real_capture_dialog_restores_open_runtime_workspace_and_sequence(qapp, tmp_path, monkeypatch, language, suffix):
    raw = (_frame(2, 1, "0208123.4", "021011.2"), _frame(2, 2, "0208123.6", "021012.0"))
    _profile, frames, commit = _time_commit(*raw)
    well = Well("well-reopen", "Reopen")
    runtime = Wits0AcquisitionRuntime(well, commit, session_id="session-reopen")
    runtime.submit_frame(frames[0])
    runtime.flush()
    runtime.create_checkpoint(created_at="2026-07-27T03:16:00Z", force=True)
    project = Project("project-reopen", "Reopen", wells={well.well_id: well})
    path = tmp_path / ("runtime" + suffix)
    ProjectController(session=ProjectSession(project=project)).save_project(path)
    reopened = ProjectController().open_project(path)
    loaded_well = reopened.project.wells[well.well_id]
    settings = QSettings(str(tmp_path / "workspace.ini"), QSettings.Format.IniFormat)
    expected = Wits0WorkspaceState(axis_mode="time", auto_follow=False, paused=True,
        follow_span=240.0, max_points=1500, acquisition_session_id="session-reopen")
    Wits0WorkspaceSettings(settings).save(well.well_id, expected)
    monkeypatch.setattr(capture, "QSettings", lambda: settings)
    monkeypatch.setattr(capture.Wits0CaptureDialog, "_load_previous_custom_profile", lambda self: commit.custom_profile)
    dialog = capture.Wits0CaptureDialog(language=language, well_provider=lambda: loaded_well)
    try:
        resumed = dialog.acquisition_runtime
        assert resumed is not None
        assert resumed.session.session_id == "session-reopen"
        assert dialog.tabs.currentWidget() is dialog.live_view
        state = dialog.live_view.workspace_state()
        assert state.axis_mode == expected.axis_mode
        assert state.auto_follow is expected.auto_follow
        assert state.paused is expected.paused
        assert state.follow_span == expected.follow_span
        assert state.max_points == expected.max_points
        before = {key: curve.values.copy() for key, curve in resumed.controller.dataset.curves.items()}
        resumed.submit_frame(frames[1])
        resumed.flush()
        assert [record.sequence for record in resumed.session.records] == [1, 2]
        assert resumed.snapshot().records_applied == 2
        for key, values in before.items():
            np.testing.assert_array_equal(resumed.controller.dataset.curves[key].values[:len(values)], values)
        dialog._persist_workspace_state()
        saved = Wits0WorkspaceSettings(QSettings(str(tmp_path / "workspace.ini"), QSettings.Format.IniFormat)).load(well.well_id)
        assert saved.acquisition_session_id == "session-reopen"
        assert saved.paused is True
    finally:
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()
