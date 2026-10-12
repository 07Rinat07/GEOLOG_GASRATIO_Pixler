import pyqtgraph as pg

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
        view.clear()
        assert len(closed) == len(plots)
    finally:
        window.close()

