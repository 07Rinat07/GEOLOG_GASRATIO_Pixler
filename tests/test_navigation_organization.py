from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.main_window import MainWindow


def _menu(window: MainWindow, key: str) -> QMenu:
    return next(
        menu
        for menu in window.findChildren(QMenu)
        if menu.menuAction().property("i18n_key") == key
    )


def _finish_deferred_navigation(qapp) -> None:
    for _ in range(4):
        qapp.processEvents()


def _assert_workspace_is_renderable(workspace, dialog) -> None:
    assert dialog.isVisible()
    assert workspace.parentWidget() is dialog
    assert dialog.layout() is not None
    assert dialog.layout().indexOf(workspace) >= 0
    assert workspace.isVisible()
    assert not workspace.isHidden()
    assert workspace.width() > 0
    assert workspace.height() > 0


def _wits_command_actions(window: MainWindow) -> tuple[QAction, ...]:
    return tuple(
        action
        for action in window.wits_protocol_menu.actions()
        if not action.isSeparator()
    )


def _wits_section_titles(window: MainWindow) -> tuple[str, ...]:
    return tuple(
        action.text()
        for action in window.wits_protocol_menu.actions()
        if action.isSeparator() and action.text()
    )


def test_utility_workspaces_are_opened_from_purpose_specific_menus(qapp) -> None:
    window = MainWindow(language=AppLanguage.RU)
    window.show()
    _finish_deferred_navigation(qapp)

    assert window.tabs.indexOf(window.file_workspace) == -1
    assert window.tabs.indexOf(window.interpretation_report_workspace) == -1
    assert window.tabs.count() == 3

    tools_menu = _menu(window, "menu.tools")
    file_menu = _menu(window, "menu.file")
    view_menu = _menu(window, "menu.view")
    print_menu = _menu(window, "menu.print")
    help_menu = _menu(window, "menu.help")

    assert window.file_workspace_action in tools_menu.actions()
    assert window.file_workspace_action not in file_menu.actions()
    assert window.file_workspace_action not in view_menu.actions()
    assert window.file_workspace_action.text() == "Файлы / PDF / Калькулятор"

    report_menu_action = window.interpretation_reports_menu.menuAction()
    assert report_menu_action in print_menu.actions()
    assert window.interpretation_reports_menu.title() == "Отчёты по интерпретации"
    assert window.interpretation_reports_menu.actions() == [
        window.gas_interpretation_report_action,
        window.interpretation_report_action,
    ]
    assert window.interpretation_report_action.text() == "Полный геологический отчёт..."

    assert help_menu.actions()[0] is window.help_center_action
    assert window.help_center_action.text() == "Документация и инструкции..."

    window.file_workspace_action.trigger()
    window.gas_interpretation_report_action.trigger()
    window.help_center_action.trigger()
    _finish_deferred_navigation(qapp)

    _assert_workspace_is_renderable(
        window.file_workspace,
        window.file_workspace_dialog,
    )
    _assert_workspace_is_renderable(
        window.interpretation_report_workspace,
        window.interpretation_report_dialog,
    )
    assert window.help_center_dialog.isVisible()
    assert window.help_center_dialog.current_section() == "overview"

    window.file_workspace_dialog.close()
    window.interpretation_report_dialog.close()
    _finish_deferred_navigation(qapp)
    window.file_workspace_action.trigger()
    window.gas_interpretation_report_action.trigger()
    _finish_deferred_navigation(qapp)

    _assert_workspace_is_renderable(
        window.file_workspace,
        window.file_workspace_dialog,
    )
    _assert_workspace_is_renderable(
        window.interpretation_report_workspace,
        window.interpretation_report_dialog,
    )

    window.change_language(AppLanguage.EN)
    _finish_deferred_navigation(qapp)

    assert window.file_workspace_action.text() == "Files / PDF / Calculator"
    assert window.interpretation_reports_menu.title() == "Interpretation reports"
    assert window.gas_interpretation_report_action.text() == "Mud-gas interpretation..."
    assert window.interpretation_report_action.text() == "Full geological report..."
    assert window.help_center_action.text() == "Documentation and instructions..."
    assert window.help_center_dialog.windowTitle() == "Documentation and instructions"

    window.help_center_dialog.close()
    window.interpretation_report_dialog.close()
    window.file_workspace_dialog.close()
    window.close()


def test_wits_commands_are_collected_in_top_level_menu_after_tools(qapp) -> None:
    window = MainWindow(language=AppLanguage.RU)
    window.show()
    _finish_deferred_navigation(qapp)

    file_menu = _menu(window, "menu.file")
    tools_menu = _menu(window, "menu.tools")
    expected_actions = (
        window.inspect_witsml_action,
        window.import_witsml_data_action,
        window.open_witsml1411_action,
        window.open_etp12_action,
        window.capture_wits0_action,
    )

    assert window.wits_protocol_menu.objectName() == "witsProtocolMenu"
    assert window.wits_protocol_action is window.wits_protocol_menu.menuAction()
    assert window.wits_protocol_action.objectName() == "witsProtocolMenuAction"
    assert window.wits_protocol_action.text() == "WITS"
    assert window.wits_protocol_menu.accessibleName() == "Центр WITS"
    assert "потоковые данные" in window.wits_protocol_action.toolTip()
    assert not hasattr(window, "wits_protocol_button")

    menu_bar_actions = window.menuBar().actions()
    tools_index = menu_bar_actions.index(tools_menu.menuAction())
    assert menu_bar_actions[tools_index + 1] is window.wits_protocol_action

    assert _wits_command_actions(window) == expected_actions
    assert _wits_section_titles(window) == (
        "Файлы WITSML 2.x",
        "Сетевые подключения",
        "Поток WITS Level 0",
    )
    assert all(action not in file_menu.actions() for action in expected_actions)
    assert all(not action.icon().isNull() for action in expected_actions)

    window.close()


def test_wits_menu_preserves_all_existing_command_handlers(qapp, monkeypatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(
        MainWindow,
        "open_witsml_inventory",
        lambda self, source=None: called.append("inventory"),
    )
    monkeypatch.setattr(
        MainWindow,
        "open_witsml_data_import",
        lambda self, source=None: called.append("import"),
    )
    monkeypatch.setattr(
        MainWindow,
        "open_witsml1411_store",
        lambda self: called.append("soap"),
    )
    monkeypatch.setattr(
        MainWindow,
        "open_etp12_session",
        lambda self: called.append("etp"),
    )
    monkeypatch.setattr(
        MainWindow,
        "open_wits0_capture",
        lambda self: called.append("wits0"),
    )

    window = MainWindow(language=AppLanguage.EN)
    window.show()
    _finish_deferred_navigation(qapp)

    for action in _wits_command_actions(window):
        action.trigger()

    assert called == ["inventory", "import", "soap", "etp", "wits0"]
    window.close()


def test_wits_menu_retranslates_without_recreating_commands(qapp) -> None:
    window = MainWindow(language=AppLanguage.RU)
    window.show()
    _finish_deferred_navigation(qapp)
    original_actions = _wits_command_actions(window)

    window.change_language(AppLanguage.KK)
    _finish_deferred_navigation(qapp)

    assert window.wits_protocol_action.text() == "WITS"
    assert window.wits_protocol_menu.accessibleName() == "WITS орталығы"
    assert "ағындық деректер" in window.wits_protocol_action.toolTip()
    assert _wits_section_titles(window) == (
        "WITSML 2.x файлдары",
        "Желілік қосылымдар",
        "WITS Level 0 ағыны",
    )
    assert _wits_command_actions(window) == original_actions

    window.change_language(AppLanguage.EN)
    _finish_deferred_navigation(qapp)

    assert window.wits_protocol_action.text() == "WITS"
    assert window.wits_protocol_menu.accessibleName() == "WITS centre"
    assert "streaming data" in window.wits_protocol_action.toolTip()
    assert _wits_section_titles(window) == (
        "WITSML 2.x files",
        "Network connections",
        "WITS Level 0 stream",
    )
    assert _wits_command_actions(window) == original_actions

    window.close()
