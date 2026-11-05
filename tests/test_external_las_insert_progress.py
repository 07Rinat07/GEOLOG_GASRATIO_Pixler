from types import SimpleNamespace
from threading import Event, get_ident

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QWidget

from geoworkbench.ui import main_window


@pytest.mark.parametrize("failure", [None, "prepare", "save"])
def test_insert_reports_stages_and_rolls_back_failed_save(qapp, tmp_path, monkeypatch, failure):
    messages = []
    events = []
    output = tmp_path / "combined.las"
    selection = object()

    class Dialog:
        analysis = object()
        output_path = output
        selections = (selection,)

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    class Controller:
        def create_copy(self, analysis, selections, *, name, prepare):
            assert selections == (selection,)
            assert name == "combined"
            prepare(lambda: events.append("prepared"))
            if failure == "prepare":
                raise RuntimeError("preparation failed")
            return SimpleNamespace(inserted_mnemonics=("GR",), dataset=SimpleNamespace(dataset_id="derived"))

    class Window(QWidget):
        def __init__(self):
            super().__init__()
            self.session = SimpleNamespace(current_dataset=object())
            self.language = None
            self.external_las_insert_controller = Controller()
            self.derived_dataset_controller = SimpleNamespace(
                checkpoint=lambda: "checkpoint",
                rollback_owned=lambda checkpoint, dataset_id: events.append(("rollback", checkpoint, dataset_id)),
            )

        def _t(self, key, **kwargs):
            return key + (":" + str(kwargs.get("name")) if "name" in kwargs else "")

        def _export_current_dataset_to_path(self, path, *, show_progress):
            assert show_progress
            events.append("save")
            if failure == "save":
                raise OSError("save failed")
            return path

        def _after_external_las_insert(self, message, mnemonics):
            events.append(("completed", mnemonics))

    monkeypatch.setattr(main_window, "ExternalLasInsertDialog", Dialog)
    monkeypatch.setattr(
        main_window, "run_las_growth_analysis",
        lambda parent, label, operation, **kwargs: (events.append(label), operation())[1],
    )
    monkeypatch.setattr(main_window.QMessageBox, "information", lambda *args: messages.append(args[2]))
    monkeypatch.setattr(main_window.QMessageBox, "warning", lambda *args: messages.append(args[2]))
    window = Window()
    try:
        main_window.MainWindow.show_external_las_insert(window)
    finally:
        window.close()
    assert events[:2] == ["external_las.preparing", "prepared"]
    if failure == "prepare":
        assert len(events) == 2
        assert messages == ["preparation failed"]
    elif failure == "save":
        assert events[2] == "save"
        assert events[-1] == ("rollback", "checkpoint", "derived")
        assert messages == ["save failed"]
    else:
        assert events[2] == "save"
        assert events[-1] == ("completed", ("GR",))
        assert messages == [f"external_las.copy_completed:{output}"]


def test_las_save_keeps_gui_events_running(qapp, tmp_path):
    ready = Event()
    gui_thread = get_ident()
    worker_threads = []

    class Exporter:
        def default_las_plan(self):
            return None

        def export_current_las(self, destination, *, overwrite, plan):
            worker_threads.append(get_ident())
            assert ready.wait(3), "GUI stopped processing events during export"
            destination.write_text("saved", encoding="utf-8")
            return destination

    class Window(QWidget):
        dataset_export_controller = Exporter()

        def _t(self, key, **kwargs):
            return key

    window = Window()
    timer = QTimer(window)
    timer.setSingleShot(True)
    timer.timeout.connect(ready.set)
    timer.start(10)
    target = tmp_path / "combined.las"
    try:
        result = main_window.MainWindow._export_current_dataset_to_path(
            window, target, show_progress=True,
        )
        assert result == target
        assert result.read_text(encoding="utf-8") == "saved"
        assert worker_threads and worker_threads[0] != gui_thread
    finally:
        timer.stop()
        window.close()
