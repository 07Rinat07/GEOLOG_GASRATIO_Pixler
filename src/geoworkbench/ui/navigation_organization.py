from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QMainWindow, QMenu, QVBoxLayout, QWidget

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.help_center_dialog import HelpCenterDialog
from geoworkbench.ui.help_content import help_action_text, normalized_language


_TEXTS = {
    AppLanguage.RU: {
        "files": "Файлы / PDF / Калькулятор",
        "files_window": "Файлы, PDF и калькуляторы",
        "reports_menu": "Отчёты по интерпретации",
        "gas_report": "Интерпретация газового каротажа...",
        "gas_window": "Отчёты по интерпретации газового каротажа",
    },
    AppLanguage.KK: {
        "files": "Файлдар / PDF / Калькулятор",
        "files_window": "Файлдар, PDF және калькуляторлар",
        "reports_menu": "Интерпретация есептері",
        "gas_report": "Газ каротажын интерпретациялау...",
        "gas_window": "Газ каротажын интерпретациялау есептері",
    },
    AppLanguage.EN: {
        "files": "Files / PDF / Calculator",
        "files_window": "Files, PDF, and calculators",
        "reports_menu": "Interpretation reports",
        "gas_report": "Mud-gas interpretation...",
        "gas_window": "Mud-gas interpretation reports",
    },
}


class _WorkspaceDialog(QDialog):
    """Persistent modeless shell for a utility workspace removed from main tabs."""

    def __init__(
        self,
        workspace: QWidget,
        parent: QWidget,
        *,
        object_name: str,
        minimum_size: tuple[int, int],
    ) -> None:
        super().__init__(parent)
        self.workspace = workspace
        self.setObjectName(object_name)
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.resize(*minimum_size)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        workspace.setParent(self)
        layout.addWidget(workspace, 1)

    def ensure_workspace_visible(self) -> None:
        """Restore visibility lost when QTabWidget removes an inactive page."""

        if self.workspace.parentWidget() is not self:
            self.workspace.setParent(self)
            layout = self.layout()
            if layout is not None and layout.indexOf(self.workspace) < 0:
                layout.addWidget(self.workspace)
        self.workspace.setVisible(True)
        layout = self.layout()
        if layout is not None:
            layout.activate()


class NavigationOrganizationController(QObject):
    """Move utility workspaces to purpose-specific menus without changing their logic."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self.window: Any = window
        self.file_dialog: _WorkspaceDialog | None = None
        self.interpretation_dialog: _WorkspaceDialog | None = None
        self.help_dialog: HelpCenterDialog | None = None
        self.interpretation_reports_menu: QMenu | None = None
        self.gas_interpretation_action: QAction | None = None
        self.help_center_action: QAction | None = None
        self._installed = False

    def install(self) -> bool:
        if self._installed:
            return True
        required = (
            "tabs",
            "file_workspace",
            "interpretation_report_workspace",
            "file_workspace_action",
            "interpretation_report_action",
        )
        if any(not hasattr(self.window, name) for name in required):
            return False

        tools_menu = _menu_by_key(self.window, "menu.tools")
        print_menu = _menu_by_key(self.window, "menu.print")
        help_menu = _menu_by_key(self.window, "menu.help")
        file_menu = _menu_by_key(self.window, "menu.file")
        view_menu = _menu_by_key(self.window, "menu.view")
        if tools_menu is None or print_menu is None or help_menu is None:
            return False

        tabs = self.window.tabs
        file_workspace = self.window.file_workspace
        interpretation_workspace = self.window.interpretation_report_workspace
        for workspace in (file_workspace, interpretation_workspace):
            index = tabs.indexOf(workspace)
            if index >= 0:
                tabs.removeTab(index)
            workspace._navigation_main_window = self.window

        self.file_dialog = _WorkspaceDialog(
            file_workspace,
            self.window,
            object_name="fileToolsDialog",
            minimum_size=(1_300, 850),
        )
        self.interpretation_dialog = _WorkspaceDialog(
            interpretation_workspace,
            self.window,
            object_name="gasInterpretationReportsDialog",
            minimum_size=(1_420, 900),
        )
        self.window.file_workspace_dialog = self.file_dialog
        self.window.interpretation_report_dialog = self.interpretation_dialog

        file_action = self.window.file_workspace_action
        for menu in (file_menu, view_menu, tools_menu):
            if menu is not None:
                menu.removeAction(file_action)
        tools_menu.addSeparator()
        tools_menu.addAction(file_action)
        _replace_trigger(file_action, self.open_file_workspace)

        existing_interpretation_action = self.window.interpretation_report_action
        print_menu.removeAction(existing_interpretation_action)
        self.interpretation_reports_menu = QMenu(print_menu)
        self.interpretation_reports_menu.setObjectName("interpretationReportsMenu")
        self.gas_interpretation_action = QAction(self.window)
        self.gas_interpretation_action.setObjectName("gasInterpretationReportsAction")
        self.gas_interpretation_action.setShortcut("Ctrl+Alt+R")
        self.gas_interpretation_action.triggered.connect(self.open_interpretation_reports)
        self.interpretation_reports_menu.addAction(self.gas_interpretation_action)
        self.interpretation_reports_menu.addAction(existing_interpretation_action)
        print_menu.addMenu(self.interpretation_reports_menu)
        self.window.gas_interpretation_report_action = self.gas_interpretation_action
        self.window.interpretation_reports_menu = self.interpretation_reports_menu

        self.help_center_action = QAction(self.window)
        self.help_center_action.setObjectName("helpCenterAction")
        self.help_center_action.setShortcut("F1")
        self.help_center_action.triggered.connect(
            lambda _checked=False: self.open_help("overview")
        )
        first_action = help_menu.actions()[0] if help_menu.actions() else None
        if first_action is None:
            help_menu.addAction(self.help_center_action)
            help_menu.addSeparator()
        else:
            help_menu.insertAction(first_action, self.help_center_action)
            help_menu.insertSeparator(first_action)
        self.window.help_center_action = self.help_center_action

        language_actions = getattr(self.window, "language_actions", {})
        for action in language_actions.values():
            action.triggered.connect(
                lambda _checked=False: QTimer.singleShot(0, self.refresh_language)
            )
        self._install_direct_language_refresh()

        self._installed = True
        self.refresh_language()
        return True

    def _install_direct_language_refresh(self) -> None:
        if getattr(self.window, "_navigation_language_wrapper_installed", False):
            return
        original_change_language = getattr(self.window, "change_language", None)
        if not callable(original_change_language):
            return

        def change_language_with_navigation(language: AppLanguage) -> None:
            original_change_language(language)
            self.refresh_language()

        self.window.change_language = change_language_with_navigation
        self.window._navigation_language_wrapper_installed = True

    def refresh_language(self) -> None:
        language = normalized_language(getattr(self.window, "language", AppLanguage.RU))
        texts = _TEXTS[language]
        if hasattr(self.window, "file_workspace_action"):
            self.window.file_workspace_action.setText(texts["files"])
        if self.file_dialog is not None:
            self.file_dialog.setWindowTitle(texts["files_window"])
        if self.interpretation_reports_menu is not None:
            self.interpretation_reports_menu.setTitle(texts["reports_menu"])
        if self.gas_interpretation_action is not None:
            self.gas_interpretation_action.setText(texts["gas_report"])
        if self.interpretation_dialog is not None:
            self.interpretation_dialog.setWindowTitle(texts["gas_window"])
        if self.help_center_action is not None:
            self.help_center_action.setText(help_action_text(language))
        if self.help_dialog is not None:
            self.help_dialog.set_language(language)

    def open_file_workspace(self) -> None:
        self.refresh_language()
        if self.file_dialog is not None:
            _show_dialog(self.file_dialog)
            status_bar = getattr(self.window, "statusBar", None)
            if callable(status_bar):
                status_bar().showMessage(self.file_dialog.windowTitle())

    def open_interpretation_reports(self) -> None:
        workspace = getattr(self.window, "interpretation_report_workspace", None)
        refresh = getattr(workspace, "refresh", None)
        if callable(refresh):
            refresh()
        self.refresh_language()
        if self.interpretation_dialog is not None:
            _show_dialog(self.interpretation_dialog)

    def open_help(self, section: str = "overview") -> None:
        language = normalized_language(getattr(self.window, "language", AppLanguage.RU))
        if self.help_dialog is None:
            self.help_dialog = HelpCenterDialog(
                self.window,
                language=language,
                section=section,
            )
            self.window.help_center_dialog = self.help_dialog
        else:
            self.help_dialog.set_language(language)
            self.help_dialog.select_section(section)
        _show_dialog(self.help_dialog)


def schedule_navigation_organization(widget: QWidget) -> None:
    """Install navigation after MainWindow has finished creating menus and actions."""

    def attempt(remaining: int = 40) -> None:
        window = _main_window_for(widget)
        if window is None:
            if remaining > 0:
                QTimer.singleShot(10, lambda: attempt(remaining - 1))
            return
        controller = getattr(window, "_navigation_organization_controller", None)
        if controller is None:
            controller = NavigationOrganizationController(window)
            setattr(window, "_navigation_organization_controller", controller)
        if not controller.install() and remaining > 0:
            QTimer.singleShot(10, lambda: attempt(remaining - 1))

    QTimer.singleShot(0, attempt)


def open_help_for_widget(widget: QWidget, section: str = "overview") -> None:
    window = _main_window_for(widget)
    controller = (
        getattr(window, "_navigation_organization_controller", None)
        if window is not None
        else None
    )
    if isinstance(controller, NavigationOrganizationController):
        controller.open_help(section)
        return
    language = normalized_language(getattr(widget, "language", AppLanguage.RU))
    dialog = HelpCenterDialog(widget, language=language, section=section)
    dialog.exec()


def _main_window_for(widget: QWidget) -> QMainWindow | None:
    stored = getattr(widget, "_navigation_main_window", None)
    if isinstance(stored, QMainWindow):
        return stored
    current: QWidget | None = widget
    while current is not None:
        if isinstance(current, QMainWindow):
            return current
        current = current.parentWidget()
    top = widget.window()
    return top if isinstance(top, QMainWindow) else None


def _menu_by_key(window: QMainWindow, key: str) -> QMenu | None:
    for menu in window.findChildren(QMenu):
        if menu.menuAction().property("i18n_key") == key:
            return menu
    return None


def _replace_trigger(action: QAction, callback: Callable[[], None]) -> None:
    try:
        action.triggered.disconnect()
    except (RuntimeError, TypeError):
        pass
    action.triggered.connect(lambda _checked=False: callback())


def _show_dialog(dialog: QDialog) -> None:
    if dialog.isMinimized():
        dialog.showNormal()
    else:
        dialog.show()
    if isinstance(dialog, _WorkspaceDialog):
        dialog.ensure_workspace_visible()
    dialog.raise_()
    dialog.activateWindow()
