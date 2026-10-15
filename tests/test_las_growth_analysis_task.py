from threading import Event, get_ident

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from geoworkbench.ui.las_growth_analysis_task import run_las_growth_analysis


def test_las_analysis_runs_off_gui_thread_while_events_continue(qapp):
    parent = QWidget()
    gui_thread = get_ident()
    release = Event()
    ticks = []
    timer = QTimer(parent)

    def heartbeat():
        ticks.append(get_ident())
        release.set()

    timer.timeout.connect(heartbeat)
    timer.start(10)

    def analyze():
        assert release.wait(2.0), "GUI timer was blocked by LAS analysis"
        return get_ident()

    try:
        worker_thread = run_las_growth_analysis(parent, "Analyzing LAS", analyze)
        assert worker_thread != gui_thread
        assert ticks and all(thread == gui_thread for thread in ticks)
    finally:
        timer.stop()
        parent.close()


def test_las_analysis_errors_return_to_gui_caller(qapp):
    parent = QWidget()

    def fail():
        raise ValueError("invalid LAS schema")

    try:
        with pytest.raises(ValueError, match="invalid LAS schema"):
            run_las_growth_analysis(parent, "Analyzing LAS", fail)
    finally:
        parent.close()
