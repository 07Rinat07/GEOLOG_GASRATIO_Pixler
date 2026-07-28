from __future__ import annotations

import importlib.util
import threading
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DIALOG_SOURCE = ROOT / "src" / "geoworkbench" / "ui" / "witsml_import_dialog.py"
MAIN_SOURCE = ROOT / "src" / "geoworkbench" / "ui" / "main_window.py"


def test_main_window_registers_exact_witsml_review_commit_atomically() -> None:
    source = MAIN_SOURCE.read_text(encoding="utf-8")
    start = source.index("def open_witsml_data_import")
    block = source[start : source.index("def dragEnterEvent", start)]

    assert 'self._localized_action("shell.import_witsml_data")' in source
    assert "WitsmlProjectImportController(self.session).register(" in block
    assert "dialog.accepted_commit" in block
    assert ").commit(" not in block
    assert "session.add_dataset" not in block


def test_import_dialog_keeps_preview_and_commit_separate() -> None:
    source = DIALOG_SOURCE.read_text(encoding="utf-8")

    assert "read_witsml_channel_sets" in source
    assert "WitsmlImportReviewController" in source
    assert "self.controller.preview(" in source
    assert "self.controller.commit(" in source
    assert "self.accepted_commit" in source
    assert "ProjectSession" not in source


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None,
    reason="PySide6 is not installed in the headless test environment",
)
def test_witsml_dialog_ignores_late_task_result_after_reject(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QDialog

    from geoworkbench.services.witsml1411_profiles import Witsml1411ProfileStore
    from geoworkbench.services.witsml_credentials import (
        InMemoryWitsmlCredentialStore,
    )
    from geoworkbench.ui.witsml1411_dialog import Witsml1411Dialog

    app = QApplication.instance() or QApplication([])
    dialog = Witsml1411Dialog(
        profile_store=Witsml1411ProfileStore(tmp_path / "profiles.json"),
        credential_store=InMemoryWitsmlCredentialStore(),
    )
    started = threading.Event()
    release = threading.Event()
    callbacks: list[object] = []

    def task() -> object:
        started.set()
        release.wait(timeout=2.0)
        return object()

    worker = None
    try:
        dialog.show()
        dialog._start_task(task, callbacks.append)
        assert started.wait(timeout=2.0)
        worker = dialog._task
        assert worker is not None
        assert worker.isRunning()

        dialog.reject()

        assert dialog.result() == QDialog.DialogCode.Rejected
        assert worker.isRunning()
        assert worker.parent() is app

        release.set()
        deadline = time.monotonic() + 2.0
        while dialog._task is not None and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)

        assert dialog._task is None
        assert callbacks == []
    finally:
        release.set()
        if worker is not None:
            try:
                worker.wait(2_000)
            except RuntimeError:
                pass
        dialog.deleteLater()
        app.processEvents()


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None,
    reason="PySide6 is not installed in the headless test environment",
)
def test_witsml_import_dialog_constructs_offscreen(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QDialogButtonBox

    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.witsml_import_dialog import WitsmlImportDialog

    app = QApplication.instance() or QApplication([])
    dialog = WitsmlImportDialog(
        ROOT / "resources" / "samples" / "witsml" / "log_channel_set_2_1.xml",
        language=AppLanguage.RU,
    )
    try:
        assert dialog.package is not None
        assert dialog.failure is None
        assert dialog.channel_set_combo.count() == 1
        assert dialog.index_combo.count() == 1
        assert dialog.table.rowCount() == 3
        assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    finally:
        dialog.close()
        app.processEvents()
