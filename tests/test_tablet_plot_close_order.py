import pyqtgraph as pg
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QLabel
from shiboken6 import isValid

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.main_window import MainWindow
from test_main_window import bind_session, make_session


def test_tablet_clear_closes_pyqtgraph_before_native_parent_deletion(qapp, monkeypatch):
    window = MainWindow(language=AppLanguage.EN)
    session, _ = make_session()
    bind_session(window, session)
    window._show_current_dataset()
    view = window.tablet_view
    entries = tuple(view._rendered.values())
    plots = tuple(entry.plot for entry in entries if entry.plot is not None)
    assert plots
    closed = []
    original_close = pg.PlotWidget.close

    def close(plot):
        assert plot.plotItem is not None
        closed.append(plot)
        return original_close(plot)

    monkeypatch.setattr(pg.PlotWidget, "close", close)
    try:
        view.clear()
        assert set(closed) == set(plots)
        assert all(plot.plotItem is None for plot in plots)
        assert all(not isValid(plot) for plot in plots)
        view.clear()
        assert len(closed) == len(plots)
    finally:
        window.close()



def test_repeated_tablet_rebuild_releases_detached_plots_before_replacement(qapp):
    window = MainWindow(language=AppLanguage.EN)
    session, _ = make_session()
    bind_session(window, session)
    try:
        window._show_current_dataset()
        view = window.tablet_view
        for _ in range(4):
            previous = tuple(entry.plot for entry in view._rendered.values()
                             if entry.plot is not None)
            assert previous
            view.refresh_view()
            assert all(not isValid(plot) for plot in previous)
            assert all(isValid(entry.plot) for entry in view._rendered.values()
                       if entry.plot is not None)
            qapp.processEvents()
    finally:
        window.close()


def test_passive_group_headers_retire_before_replacement_without_global_event_pump(qapp):
    window = MainWindow(language=AppLanguage.EN)
    session, layout = make_session()
    for definition in layout.tracks:
        definition.group_title = "Measurements"
    bind_session(window, session)
    unrelated = QLabel("Unrelated deferred deletion")
    try:
        window._show_current_dataset()
        view = window.tablet_view
        assert view.group_header_titles == ("Measurements",)
        unrelated.deleteLater()
        for _ in range(4):
            previous = view._group_header_layout.itemAt(0).widget()
            assert isinstance(previous, QLabel) and isValid(previous)
            view._rebuild_group_headers()
            assert not isValid(previous)
            assert view.group_header_titles == ("Measurements",)
            assert isValid(unrelated)
        # Full refresh must also retire the last group header before the next
        # PlotWidget tree is created, without dispatching unrelated deletions.
        previous = view._group_header_layout.itemAt(0).widget()
        view.refresh_view()
        assert not isValid(previous)
        assert view.group_header_titles == ("Measurements",)
        assert isValid(unrelated)
    finally:
        if isValid(unrelated):
            QCoreApplication.sendPostedEvents(unrelated, QEvent.Type.DeferredDelete)
        window.close()


def test_empty_tablet_placeholder_retires_before_restoring_dataset(qapp):
    window = MainWindow(language=AppLanguage.EN)
    session, _ = make_session()
    bind_session(window, session)
    try:
        window._show_current_dataset()
        view = window.tablet_view
        dataset = session.current_dataset
        assert dataset is not None
        for _ in range(3):
            view.set_dataset(None)
            assert view._tracks_layout.count() == 1
            previous = view._tracks_layout.itemAt(0).widget()
            assert isinstance(previous, QLabel) and isValid(previous)
            view.set_dataset(dataset)
            assert not isValid(previous)
            assert view.rendered_track_ids == tuple(
                definition.track_id for definition in view.layout_model.visible_tracks()
            )
            assert view.rendered_track_ids
            assert all(isValid(entry.plot) for entry in view._rendered.values())
    finally:
        window.close()
