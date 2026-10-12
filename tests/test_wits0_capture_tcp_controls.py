import socket
import threading
import time

import pytest
from PySide6.QtCore import QSettings

from geoworkbench.acquisition.wits0_capture import Wits0ConnectionMode
from geoworkbench.services.localization import AppLanguage
import geoworkbench.ui.wits0_capture_dialog as capture


@pytest.mark.parametrize("language", list(AppLanguage))
def test_real_capture_controls_stop_and_restart_tcp_without_losing_raw(qapp, tmp_path, monkeypatch, language):
    settings = QSettings(str(tmp_path / "capture.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(capture, "QSettings", lambda: settings)
    payloads = (b"&&01081!!", b"&&01082!!")
    errors = []
    finished = threading.Event()
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(2)
    listener.settimeout(5.0)

    def serve():
        try:
            for payload in payloads:
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(5.0)
                    connection.sendall(payload)
                    while connection.recv(1024):
                        pass
        except Exception as exc:
            errors.append(exc)
        finally:
            finished.set()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    dialog = capture.Wits0CaptureDialog(language=language)
    engines = []
    try:
        dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData(Wits0ConnectionMode.TCP_CLIENT.value))
        dialog.host_edit.setText("127.0.0.1")
        dialog.port_spin.setValue(listener.getsockname()[1])
        raw_directory = tmp_path / "raw"
        dialog.raw_directory_edit.setText(str(raw_directory))
        dialog.disk_critical_spin.setValue(0)
        dialog.disk_warning_spin.setValue(0)
        previous_files = {}
        for payload in payloads:
            assert dialog.start_button.isEnabled()
            dialog.start_button.click()
            engine = dialog.engine
            assert engine is not None and engine.is_running
            engines.append(engine)
            assert not dialog.start_button.isEnabled()
            assert dialog.stop_button.isEnabled()
            deadline = time.monotonic() + 5.0
            while engine.snapshot().frames_received < 1 and time.monotonic() < deadline:
                qapp.processEvents()
                time.sleep(0.01)
            assert engine.snapshot().frames_received == 1
            dialog.stop_button.click()
            assert not engine.is_running
            assert dialog.start_button.isEnabled()
            assert not dialog.stop_button.isEnabled()
            current_files = {path: path.read_bytes() for path in raw_directory.rglob("*.wits")}
            assert {path: current_files[path] for path in previous_files} == previous_files
            assert [data for path, data in current_files.items() if path not in previous_files] == [payload]
            previous_files = current_files
        assert engines[0] is not engines[1]
        assert finished.wait(2.0)
        assert errors == []
        assert len(previous_files) == len(payloads)
    finally:
        for engine in engines:
            engine.stop(timeout=2.0)
        listener.close()
        worker.join(timeout=2.0)
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_real_capture_controls_keep_engine_and_raw_across_automatic_reconnect(qapp, tmp_path, monkeypatch, language):
    settings = QSettings(str(tmp_path / "reconnect.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(capture, "QSettings", lambda: settings)
    payloads = (b"&&01083!!", b"&&01084!!")
    errors = []
    finished = threading.Event()
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(2)
    listener.settimeout(10.0)

    def serve():
        try:
            for index, payload in enumerate(payloads):
                connection, _ = listener.accept()
                with connection:
                    connection.sendall(payload)
                    if index == 1:
                        connection.settimeout(10.0)
                        while connection.recv(1024):
                            pass
        except Exception as exc:
            errors.append(exc)
        finally:
            finished.set()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    dialog = capture.Wits0CaptureDialog(language=language)
    engine = None
    try:
        dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData(Wits0ConnectionMode.TCP_CLIENT.value))
        dialog.host_edit.setText("127.0.0.1")
        dialog.port_spin.setValue(listener.getsockname()[1])
        raw_directory = tmp_path / "raw-reconnect"
        dialog.raw_directory_edit.setText(str(raw_directory))
        dialog.disk_critical_spin.setValue(0)
        dialog.disk_warning_spin.setValue(0)
        dialog.start_button.click()
        engine = dialog.engine
        assert engine is not None
        deadline = time.monotonic() + 10.0
        while engine.snapshot().frames_received < 2 and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
        assert dialog.engine is engine
        assert engine.is_running
        assert engine.snapshot().connections == 2
        assert engine.snapshot().frames_received == 2
        assert not dialog.start_button.isEnabled()
        assert dialog.stop_button.isEnabled()
        dialog.stop_button.click()
        assert not engine.is_running
        assert finished.wait(2.0)
        assert errors == []
        assert sorted(path.read_bytes() for path in raw_directory.rglob("*.wits")) == sorted(payloads)
        assert dialog.start_button.isEnabled()
        assert not dialog.stop_button.isEnabled()
    finally:
        if engine is not None:
            engine.stop(timeout=2.0)
        listener.close()
        worker.join(timeout=2.0)
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()
