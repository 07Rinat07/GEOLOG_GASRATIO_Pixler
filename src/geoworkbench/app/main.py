from __future__ import annotations

import logging
from pathlib import Path
import sys

from PySide6.QtCore import (
    QEvent,
    QStandardPaths,
    QtMsgType,
    qInstallMessageHandler,
)
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QInputDialog

from geoworkbench import __version__
from geoworkbench.services.application_logging import (
    ApplicationLogManager,
    configure_application_logging,
    install_python_exception_hooks,
)
from geoworkbench.services.localization import (
    LANGUAGE_NAMES,
    AppLanguage,
    LanguageSettings,
    Localizer,
)


class DiagnosticApplication(QApplication):
    """QApplication that records exceptions escaping Qt event handlers."""

    def __init__(self, arguments: list[str]) -> None:
        super().__init__(arguments)
        self._log_manager: ApplicationLogManager | None = None

    def set_log_manager(self, manager: ApplicationLogManager) -> None:
        self._log_manager = manager

    def notify(self, receiver, event: QEvent) -> bool:  # type: ignore[override]
        try:
            return super().notify(receiver, event)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:  # Qt must not hide application exceptions.
            manager = self._log_manager
            if manager is not None:
                manager.exception(
                    "qt.event.exception",
                    exc,
                    context={
                        "receiver": type(receiver).__name__ if receiver is not None else "None",
                        "object_name": (
                            receiver.objectName()
                            if receiver is not None and hasattr(receiver, "objectName")
                            else ""
                        ),
                        "event_type": int(event.type()) if event is not None else -1,
                    },
                )
                manager.flush()
            # Returning False prevents an exception from tearing down the Qt event
            # dispatcher.  The operation that failed remains cancelled and the log
            # contains the complete traceback for support analysis.
            return False


def _install_qt_message_logging(manager: ApplicationLogManager) -> None:
    level_by_type = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    def handler(
        message_type: QtMsgType,
        context: object,
        message: str,
    ) -> None:
        manager.event(
            "qt.message",
            level=level_by_type.get(message_type, logging.INFO),
            message=message,
            category=getattr(context, "category", "") or "",
            file=getattr(context, "file", "") or "",
            line=getattr(context, "line", 0),
            function=getattr(context, "function", "") or "",
        )
        if message_type == QtMsgType.QtFatalMsg:
            manager.flush()

    qInstallMessageHandler(handler)


def _configure_readable_tooltips(app: QApplication) -> None:
    """Force readable tooltips independently of the Windows/global palette.

    Some Windows themes combine a white tooltip base with inherited white text,
    producing an apparently blank highlighted sentence.  Set both palette roles
    and a narrowly scoped QToolTip stylesheet so ordinary labels and dialogs keep
    their existing theme while help text remains legible.
    """

    palette = app.palette()
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#fffbe6"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#0f172a"))
    app.setPalette(palette)
    app.setStyleSheet(
        app.styleSheet()
        + "\nQToolTip { color:#0f172a; background-color:#fffbe6; "
        "border:1px solid #64748b; padding:4px 6px; opacity:255; }"
    )


def main() -> int:
    app = DiagnosticApplication(sys.argv)
    _configure_readable_tooltips(app)
    app.setApplicationName("GEOLOG GASRATIO@Pixler")
    app.setOrganizationName("GeoLog")

    log_root = Path(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    ) / "logs"
    log_manager = configure_application_logging(
        log_root,
        application_version=__version__,
    )
    app.set_log_manager(log_manager)
    install_python_exception_hooks(log_manager)
    _install_qt_message_logging(log_manager)
    app.aboutToQuit.connect(log_manager.close)

    log_manager.event("application.qt.created", arguments=len(sys.argv))
    try:
        from geoworkbench.printing.unicode_support import (
            configure_application_unicode_fonts,
        )
        from geoworkbench.ui.branding import application_icon
        from geoworkbench.ui.main_window import MainWindow
        from geoworkbench.ui.startup_splash import StartupSplash
    except BaseException as exc:
        log_manager.exception("application.module_import.failed", exc)
        log_manager.flush()
        raise

    app.setWindowIcon(application_icon())
    configure_application_unicode_fonts(app)
    settings = LanguageSettings.system()
    language = settings.current()
    if language is None:
        localizer = Localizer.create(AppLanguage.RU)
        names = [LANGUAGE_NAMES[item] for item in AppLanguage]
        selected, accepted = QInputDialog.getItem(
            None,
            localizer.text("language.first.title"),
            localizer.text("language.first.prompt"),
            names,
            0,
            False,
        )
        language = next(
            (item for item, name in LANGUAGE_NAMES.items() if name == selected),
            AppLanguage.RU,
        )
        if accepted:
            settings.save(language)
    startup_localizer = Localizer.create(language)
    splash = StartupSplash(language)
    splash.show()
    app.processEvents()
    splash.set_stage(startup_localizer.text("startup.stage.catalogs"), 38)
    app.processEvents()
    try:
        window = MainWindow(language=language, language_settings=settings)
        window.show()
        app.processEvents()
        splash.finish()
        log_manager.event("application.main_window.ready", language=language.value)
        return app.exec()
    except BaseException as exc:
        log_manager.exception("application.startup.failed", exc)
        log_manager.flush()
        raise


if __name__ == "__main__":
    raise SystemExit(main())
