from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "geoworkbench" / "ui" / "wits0_capture_dialog.py"
MAIN_WINDOW = ROOT / "src" / "geoworkbench" / "ui" / "main_window.py"


def test_wits0_capture_ui_keeps_socket_work_outside_qt_thread() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "Wits0CaptureEngine" in source
    assert "QTimer" in source
    assert ".drain_events(" in source
    assert "socket.socket" not in source
    assert ".recv(" not in source
    assert ".accept(" not in source


def test_wits0_capture_ui_is_resizable_and_keeps_actions_outside_scroll_area() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "QScrollArea" in source
    assert "fit_window_to_screen(" in source
    assert "self.setMinimumSize(640, 480)" not in source
    assert "root.addWidget(self.scroll_area, 1)" in source
    assert "actions = QGridLayout()" in source
    assert source.index("root.addWidget(self.scroll_area, 1)") < source.index(
        "root.addLayout(actions)"
    )


def test_main_window_exposes_modeless_wits0_capture_action() -> None:
    source = MAIN_WINDOW.read_text(encoding="utf-8")

    assert 'self._localized_action("shell.capture_wits0")' in source
    assert "def open_wits0_capture" in source
    assert "dialog.show()" in source
    assert "dialog.exec()" not in source[source.index("def open_wits0_capture") : source.index("def open_witsml_inventory")]


def test_wits0_capture_exposes_operator_help_and_fullscreen_monitor() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "self.help_text = QPlainTextEdit(self)" in source
    assert "_operator_help_document(language)" in source
    assert "def _apply_connection_tooltips(" in source
    assert "self.live_view.fullScreenRequested.connect(self._set_live_fullscreen)" in source
    assert "def _set_live_fullscreen(" in source
    assert "showFullScreen()" in source
    assert "def _restore_live_view_from_fullscreen(" in source


def test_wits0_capture_ui_connects_review_to_bounded_acquisition_runtime() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    main_source = MAIN_WINDOW.read_text(encoding="utf-8")

    assert "Wits0AcquisitionRuntime" in source
    assert "Wits0AcquisitionConfig" in source
    assert "Wits0BackpressurePolicy.DRAIN_THEN_RETRY" in source
    assert "def _start_acquisition" in source
    assert "def _flush_acquisition" in source
    assert "def _close_acquisition" in source
    assert "well_provider" in source
    assert "on_dataset_changed" in source
    assert "well_provider=lambda: self.session.current_well" in main_source
    assert "def _on_wits0_dataset_changed" in main_source


def test_wits0_capture_blocks_persistent_start_before_runtime_when_preview_is_truncated() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    start = source[
        source.index("def _start_acquisition")
        : source.index("def _flush_acquisition")
    ]

    assert "self.live_preview.backfill_boundary" in start
    assert "boundary.truncated" in start
    assert '"wits0.acquisition_preview_truncated"' in start
    assert '"wits0.acquisition_preview_truncated_event"' in start
    assert start.index("boundary.truncated") < start.index("Wits0AcquisitionRuntime(")


def test_wits0_capture_ui_exposes_reliability_and_restart_recovery_controls() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "Wits0DiskSpacePolicy" in source
    assert "Wits0RawRetentionPolicy" in source
    assert "Wits0RemoteBindPolicy" in source
    assert "allowed_peer_networks" in source
    assert "wits0.remote_bind_warning" in source
    assert "inspect_wits0_raw_directory" in source
    assert "wits0.raw_directory_adopt_warning" in source
    assert "submit_connection_event" in source
    assert "def _restore_open_acquisition_session" in source
    assert "restore_wits0_import_review_commit" in source
    assert "Wits0WorkspaceSettings" in source
    assert "def _persist_workspace_state" in source


def test_wits0_capture_setting_int_rejects_corrupt_values(tmp_path: Path) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QSettings

    from geoworkbench.ui.wits0_capture_dialog import (
        _network_values,
        _setting_bool,
        _setting_int,
    )

    settings = QSettings(str(tmp_path / "wits0-settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("valid", "4096")
    settings.setValue("invalid", "not-an-integer")
    settings.setValue("boolean", True)

    assert _setting_int(settings, "valid", 10) == 4096
    assert _setting_int(settings, "invalid", 10) == 10
    assert _setting_int(settings, "boolean", 10) == 10
    assert _setting_int(settings, "missing", 10) == 10

    settings.setValue("enabled", "true")
    settings.setValue("disabled", "0")
    settings.setValue("corrupt_bool", "sometimes")
    assert _setting_bool(settings, "enabled", False)
    assert not _setting_bool(settings, "disabled", True)
    assert _setting_bool(settings, "corrupt_bool", True)
    assert _network_values("192.168.10.0/24, 10.0.0.5/32; 172.16.0.0/16") == (
        "192.168.10.0/24",
        "10.0.0.5/32",
        "172.16.0.0/16",
    )


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None,
    reason="PySide6 is not installed in the headless test environment",
)
def test_wits0_capture_dialog_constructs_offscreen(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.wits0_capture_dialog import Wits0CaptureDialog

    app = QApplication.instance() or QApplication([])
    dialog = Wits0CaptureDialog(language=AppLanguage.RU)
    try:
        assert dialog.windowTitle()
        assert dialog.start_button.isEnabled()
        assert not dialog.stop_button.isEnabled()
        assert dialog.help_text.isReadOnly()
        assert dialog.help_text.toPlainText()
        assert dialog.host_edit.toolTip()
        assert dialog.port_spin.toolTip()
        assert dialog.raw_directory_edit.toolTip()
        dialog.field_preset_button.click()
        assert dialog.mode_combo.currentData() == "tcp_client"
        assert dialog.host_edit.text() == "192.168.0.100"
        assert dialog.port_spin.value() == 2041
        assert not dialog.allowed_networks_edit.text()
        assert not dialog.allow_wildcard_bind_check.isChecked()
    finally:
        dialog.close()
        app.processEvents()


def test_navigation_controller_remains_single_owner_of_dedicated_wits_menu() -> None:
    source = MAIN_WINDOW.read_text(encoding="utf-8")

    assert 'wits_menu = self._add_localized_menu("menu.wits")' not in source
    for action in (
        "inspect_witsml_action",
        "import_witsml_data_action",
        "open_witsml1411_action",
        "open_etp12_action",
        "capture_wits0_action",
    ):
        assert f"file_menu.addAction(self.{action})" in source


def test_wits0_capture_reports_synchronous_startup_failures() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    start = source[source.index("def _start_capture") : source.index("def _prepare_raw_directory")]

    assert "except (OSError, RuntimeError, ValueError) as exc:" in start
    assert '"wits0.start_failed_event"' in start
    assert "self.engine = engine" in start
    assert start.index("engine.start()") < start.index("self.engine = engine")
