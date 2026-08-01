from __future__ import annotations

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
    assert window.help_center_action.text() == "Documentation and instructions..."
    assert window.help_center_dialog.windowTitle() == "Documentation and instructions"

    window.help_center_dialog.close()
    window.interpretation_report_dialog.close()
    window.file_workspace_dialog.close()
    window.close()
