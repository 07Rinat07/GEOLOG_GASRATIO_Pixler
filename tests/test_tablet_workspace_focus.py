"""Workspace focus hides chrome without disabling form editing or navigation."""

import numpy as np
import pytest

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.main_window import MainWindow
from test_main_window import bind_session, make_session


@pytest.mark.parametrize("language", list(AppLanguage))
def test_tablet_workspace_focus_restores_chrome_and_keeps_form_editing(qapp, language):
    window = MainWindow()
    session, layout = make_session()
    bind_session(window, session)
    window._show_workspace(window.tablet_view)
    window.resize(1366, 768)
    window.show()
    try:
        qapp.processEvents()
        action = window.tablet_workspace_focus_action
        view = window.tablet_view
        assert action.isEnabled()
        assert action.shortcut().toString() == "F11"
        assert view._workspace_focus_button.defaultAction() is action
        assert view._workspace_focus_button.isVisible()
        assert not window.main_toolbar.isHidden()
        depth = view.visible_depth_range
        data = session.current_dataset.curve_by_mnemonic("ROP").values.copy()
        before_height = view.height()

        view._workspace_focus_button.click()
        qapp.processEvents()
        view._restore_visible_depth_after_resize()
        qapp.processEvents()
        assert action.isChecked()
        assert window.main_toolbar.isHidden()
        assert window.tabs.tabBar().isHidden()
        assert window.toolbar_host.isHidden()
        assert window.menuBar().isVisible()
        assert view._workspace_focus_button.isVisible()
        assert view.height() > before_height
        assert view._compact_screen()
        assert view.visible_depth_range == depth

        window.tablet_edit_mode_action.setChecked(True)
        qapp.processEvents()
        assert not window.toolbar_host.isHidden()
        assert not window.form_edit_toolbar.isHidden()
        assert window.main_toolbar.isHidden()
        assert window.tablet_edit_mode_action.isChecked()

        view.set_language(language)
        window.resize(1024, 768)
        qapp.processEvents()
        assert view._workspace_focus_button.isVisible()
        assert view._workspace_focus_active
        view._workspace_focus_button.click()
        qapp.processEvents()
        assert not action.isChecked()
        assert not window.main_toolbar.isHidden()
        assert not window.tabs.tabBar().isHidden()
        assert not window.form_edit_toolbar.isHidden()
        assert window.tablet_edit_mode_action.isChecked()

        action.setChecked(True)
        window.tabs.setCurrentWidget(window.curve_view)
        qapp.processEvents()
        assert not action.isChecked() and not action.isEnabled()
        assert not window.main_toolbar.isHidden()
        assert not window.tabs.tabBar().isHidden()
        assert not view._workspace_focus_active
        assert session.current_tablet_layout is layout
        np.testing.assert_array_equal(session.current_dataset.curve_by_mnemonic("ROP").values, data)
    finally:
        window.close()
