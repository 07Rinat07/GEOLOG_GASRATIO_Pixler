import pyqtgraph as pg
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QLabel, QWidgetAction
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


@pytest.mark.parametrize("explicit_cleanup", (False, True))
def test_plot_options_menus_follow_native_window_ownership(qapp, explicit_cleanup):
    """The real tablet and CurveView must not leave parentless menus behind."""
    window = MainWindow(language=AppLanguage.EN)
    session, _ = make_session()
    bind_session(window, session)
    try:
        window._show_current_dataset()
        view = window.tablet_view
        curve_plot = window.curve_view._plot
        plots = (curve_plot, *(entry.plot for entry in view._rendered.values()
                               if entry.plot is not None))
        assert len(plots) > 1
        items = tuple(plot.getPlotItem() for plot in plots)
        menus = (items[0].ctrlMenu,)
        controls = tuple(item.control_root for item in items[1:])
        control_groups = tuple(
            group for item in items[1:] for group in (
                item.ctrl.transformGroup, item.ctrl.decimateGroup, item.ctrl.averageGroup,
                item.ctrl.alphaGroup, item.ctrl.gridGroup, item.ctrl.pointsGroup,
            )
        )
        assert all(item.ctrlMenu is None for item in items[1:])
        assert all(root.parentWidget() is plot for root, plot in zip(controls, plots[1:], strict=True))
        assert all(root.isHidden() for root in controls)
        assert all(isValid(obj) for obj in (*controls, *control_groups))
        assert all(
            root.isAncestorOf(group)
            for root, item in zip(controls, items[1:], strict=True)
            for group in (item.ctrl.transformGroup, item.ctrl.decimateGroup, item.ctrl.averageGroup,
                          item.ctrl.alphaGroup, item.ctrl.gridGroup, item.ctrl.pointsGroup)
        )
        actions = tuple(
            action for menu in menus for entry in menu.actions()
            if entry.menu() is not None
            for action in entry.menu().actions()
            if isinstance(action, QWidgetAction)
        )
        widgets = tuple(action.defaultWidget() for action in actions)
        assert len(actions) == 6
        assert len(control_groups) == 6 * (len(plots) - 1)
        assert all(isValid(obj) for obj in (*items, *menus, *actions, *widgets))
        assert menus[0].parentWidget() is curve_plot
        assert all(menu.windowType() == Qt.WindowType.Popup for menu in menus)
        # CurveView continues to expose the actual upstream menu and controls;
        # tablet tracks keep their existing disabled context-menu policy.
        assert curve_plot.getPlotItem().getMenu() is menus[0]
        assert curve_plot.getPlotItem().menuEnabled()
        assert all(not item.menuEnabled() for item in items[1:])
        if explicit_cleanup:
            view.clear()
            assert all(not isValid(plot) for plot in plots[1:])
            assert all(not isValid(obj) for obj in (*controls, *control_groups))
            curve_plot.close()
            assert curve_plot.plotItem is None
            # Upstream close detaches PlotWidget itself; restore its owning
            # widget just as the production tablet disposal path does.
            curve_plot.setParent(window.curve_view)
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)
        assert not isValid(window)
        assert all(not isValid(plot) for plot in plots)
        assert all(not isValid(obj) for obj in (*items, *menus, *actions, *widgets, *controls, *control_groups))
    finally:
        if isValid(window):
            window.close()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)
