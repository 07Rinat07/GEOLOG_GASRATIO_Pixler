from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import QObject, QPointF, QRectF, QSize, QTimer, Qt
from PySide6.QtGui import QAction, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

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
        "wits_accessible": "Центр WITS",
        "wits_tooltip": "WITS, WITSML и ETP: файлы, подключения и потоковые данные",
        "wits_files": "Файлы WITSML 2.x",
        "wits_connections": "Сетевые подключения",
        "wits_stream": "Поток WITS Level 0",
    },
    AppLanguage.KK: {
        "files": "Файлдар / PDF / Калькулятор",
        "files_window": "Файлдар, PDF және калькуляторлар",
        "reports_menu": "Интерпретация есептері",
        "gas_report": "Газ каротажын интерпретациялау...",
        "gas_window": "Газ каротажын интерпретациялау есептері",
        "wits_accessible": "WITS орталығы",
        "wits_tooltip": "WITS, WITSML және ETP: файлдар, қосылымдар және ағындық деректер",
        "wits_files": "WITSML 2.x файлдары",
        "wits_connections": "Желілік қосылымдар",
        "wits_stream": "WITS Level 0 ағыны",
    },
    AppLanguage.EN: {
        "files": "Files / PDF / Calculator",
        "files_window": "Files, PDF, and calculators",
        "reports_menu": "Interpretation reports",
        "gas_report": "Mud-gas interpretation...",
        "gas_window": "Mud-gas interpretation reports",
        "wits_accessible": "WITS centre",
        "wits_tooltip": "WITS, WITSML, and ETP: files, connections, and streaming data",
        "wits_files": "WITSML 2.x files",
        "wits_connections": "Network connections",
        "wits_stream": "WITS Level 0 stream",
    },
}

_WITS_ACTION_NAMES = (
    "inspect_witsml_action",
    "import_witsml_data_action",
    "open_witsml1411_action",
    "open_etp12_action",
    "capture_wits0_action",
)


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


class _WitsMenuButton(QToolButton):
    """Distinct menu-bar entry point for all WITS/WITSML/ETP commands."""

    def __init__(self, menu: QMenu, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("witsProtocolButton")
        self.setText("WITS")
        self.setMenu(menu)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIcon(_wits_icon(self.palette()))
        self.setIconSize(QSize(22, 22))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAutoRaise(False)
        self.setMinimumSize(96, 30)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            """
            QToolButton#witsProtocolButton {
                border: 1px solid palette(highlight);
                border-left: 4px solid palette(highlight);
                border-radius: 6px;
                padding: 3px 18px 3px 7px;
                margin: 1px 6px 1px 4px;
                background: palette(button);
                color: palette(button-text);
                font-weight: 700;
            }
            QToolButton#witsProtocolButton:hover {
                background: palette(alternate-base);
            }
            QToolButton#witsProtocolButton:pressed {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
            QToolButton#witsProtocolButton::menu-indicator {
                subcontrol-origin: padding;
                subcontrol-position: right center;
                right: 5px;
            }
            """
        )


def _wits_icon(palette: QPalette) -> QIcon:
    pixmap = QPixmap(28, 28)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        accent = palette.color(QPalette.ColorRole.Highlight)
        ink = palette.color(QPalette.ColorRole.ButtonText)
        painter.setPen(QPen(accent, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(7.0, 7.0), QPointF(20.0, 14.0))
        painter.drawLine(QPointF(7.0, 21.0), QPointF(20.0, 14.0))
        painter.setBrush(accent)
        painter.drawEllipse(QRectF(3.5, 3.5, 7.0, 7.0))
        painter.drawEllipse(QRectF(3.5, 17.5, 7.0, 7.0))
        painter.setBrush(palette.color(QPalette.ColorRole.Button))
        painter.drawEllipse(QRectF(16.0, 10.0, 8.0, 8.0))
        painter.setPen(QPen(ink, 1.5))
        painter.drawLine(QPointF(18.5, 13.0), QPointF(21.5, 15.0))
        painter.drawLine(QPointF(18.5, 15.0), QPointF(21.5, 13.0))
    finally:
        painter.end()
    return QIcon(pixmap)


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
        self.wits_menu: QMenu | None = None
        self.wits_button: _WitsMenuButton | None = None
        self.wits_files_section: QAction | None = None
        self.wits_connections_section: QAction | None = None
        self.wits_stream_section: QAction | None = None
        self.wits_actions: tuple[QAction, ...] = ()
        self._wits_corner_host: QWidget | None = None
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
            *_WITS_ACTION_NAMES,
        )
        if any(not hasattr(self.window, name) for name in required):
            return False

        tools_menu = _menu_by_key(self.window, "menu.tools")
        print_menu = _menu_by_key(self.window, "menu.print")
        help_menu = _menu_by_key(self.window, "menu.help")
        file_menu = _menu_by_key(self.window, "menu.file")
        view_menu = _menu_by_key(self.window, "menu.view")
        if tools_menu is None or print_menu is None or help_menu is None or file_menu is None:
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

        self._install_wits_button(file_menu)

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

    def _install_wits_button(self, file_menu: QMenu) -> None:
        actions = tuple(
            cast(QAction, getattr(self.window, name)) for name in _WITS_ACTION_NAMES
        )
        self.wits_actions = actions
        for action in actions:
            file_menu.removeAction(action)

        self.wits_menu = QMenu(self.window)
        self.wits_menu.setObjectName("witsProtocolMenu")
        self.wits_menu.setToolTipsVisible(True)
        self.wits_files_section = self.wits_menu.addSection("")
        self.wits_menu.addAction(actions[0])
        self.wits_menu.addAction(actions[1])
        self.wits_menu.addSeparator()
        self.wits_connections_section = self.wits_menu.addSection("")
        self.wits_menu.addAction(actions[2])
        self.wits_menu.addAction(actions[3])
        self.wits_menu.addSeparator()
        self.wits_stream_section = self.wits_menu.addSection("")
        self.wits_menu.addAction(actions[4])

        standard_pixmaps = (
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            QStyle.StandardPixmap.SP_DialogOpenButton,
            QStyle.StandardPixmap.SP_DriveNetIcon,
            QStyle.StandardPixmap.SP_DriveNetIcon,
            QStyle.StandardPixmap.SP_MediaPlay,
        )
        for action, pixmap in zip(actions, standard_pixmaps, strict=True):
            if action.icon().isNull():
                action.setIcon(self.window.style().standardIcon(pixmap))

        self.wits_button = _WitsMenuButton(self.wits_menu, self.window.menuBar())
        self._wits_corner_host = _place_menu_bar_button(self.window, self.wits_button)
        self.window.wits_protocol_menu = self.wits_menu
        self.window.wits_protocol_button = self.wits_button
        self.window.wits_protocol_actions = self.wits_actions

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
        if self.wits_menu is not None:
            self.wits_menu.setTitle(texts["wits_accessible"])
        if self.wits_button is not None:
            self.wits_button.setToolTip(texts["wits_tooltip"])
            self.wits_button.setStatusTip(texts["wits_tooltip"])
            self.wits_button.setAccessibleName(texts["wits_accessible"])
            self.wits_button.setAccessibleDescription(texts["wits_tooltip"])
        if self.wits_files_section is not None:
            self.wits_files_section.setText(texts["wits_files"])
        if self.wits_connections_section is not None:
            self.wits_connections_section.setText(texts["wits_connections"])
        if self.wits_stream_section is not None:
            self.wits_stream_section.setText(texts["wits_stream"])

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


def _place_menu_bar_button(window: QMainWindow, button: QToolButton) -> QWidget:
    menu_bar = window.menuBar()
    corner = Qt.Corner.TopRightCorner
    existing = menu_bar.cornerWidget(corner)
    if existing is None:
        menu_bar.setCornerWidget(button, corner)
        button.show()
        menu_bar.updateGeometry()
        return button

    host = QWidget(menu_bar)
    host.setObjectName("menuBarCornerActions")
    layout = QHBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    existing.setParent(host)
    layout.addWidget(existing)
    layout.addWidget(button)
    menu_bar.setCornerWidget(host, corner)
    host.show()
    button.show()
    menu_bar.updateGeometry()
    return host


def _show_dialog(dialog: QDialog) -> None:
    if dialog.isMinimized():
        dialog.showNormal()
    else:
        dialog.show()
    if isinstance(dialog, _WorkspaceDialog):
        dialog.ensure_workspace_visible()
    dialog.raise_()
    dialog.activateWindow()
