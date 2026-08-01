from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QWidget,
)

from geoworkbench.data.las_adapter import LasExportError
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.help_content import normalized_language


class CloseChoice(StrEnum):
    SAVE_PROJECT = "save_project"
    EXPORT_LAS = "export_las"
    DISCARD = "discard"
    CANCEL = "cancel"


_TEXTS = {
    AppLanguage.RU: {
        "project": "Проект",
        "well": "Скважина",
        "dataset": "Данные",
        "source": "Источник",
        "saved": "Сохранено",
        "modified": "Изменено",
        "empty": "—",
        "format": "Формат",
        "rows": "Строк",
        "curves": "Кривых",
        "project_path": "Файл проекта",
        "save_target": "Сохранение",
        "save_project_target": "проект",
        "save_copy_target": "проект или LAS-копия",
        "close_title": "Есть несохранённые данные",
        "close_text": "Изменения текущей рабочей сессии ещё не сохранены.",
        "close_info": (
            "Сохранение проекта сохраняет данные, формы и оформление. "
            "Экспорт LAS сохраняет только текущий набор кривых и заголовков. "
            "Исходные GeoScape, GS2 и Paradox-файлы автоматически не изменяются."
        ),
        "save_project": "Сохранить проект",
        "export_las": "Экспортировать LAS-копию",
        "discard": "Не сохранять",
        "cancel": "Отмена",
        "export_title": "Сохранить изменённые данные в LAS",
        "overwrite_title": "Подтверждение перезаписи",
        "overwrite_text": "Файл «{name}» уже существует. Перезаписать его?",
        "export_failed": "Не удалось сохранить LAS-копию:\n{error}",
        "export_done_title": "LAS-копия сохранена",
        "export_done": (
            "Текущие кривые и заголовки сохранены в:\n{path}\n\n"
            "Формы, оформление и остальные данные проекта в LAS не входят. "
            "Закрыть программу без сохранения проекта?"
        ),
    },
    AppLanguage.KK: {
        "project": "Жоба",
        "well": "Ұңғыма",
        "dataset": "Деректер",
        "source": "Дереккөз",
        "saved": "Сақталды",
        "modified": "Өзгертілді",
        "empty": "—",
        "format": "Пішім",
        "rows": "Жол",
        "curves": "Қисық",
        "project_path": "Жоба файлы",
        "save_target": "Сақтау",
        "save_project_target": "жоба",
        "save_copy_target": "жоба немесе LAS көшірмесі",
        "close_title": "Сақталмаған деректер бар",
        "close_text": "Ағымдағы жұмыс сеансындағы өзгерістер әлі сақталмаған.",
        "close_info": (
            "Жобаны сақтау деректерді, пішіндерді және безендіруді сақтайды. "
            "LAS экспорты тек ағымдағы қисықтар мен тақырыптарды сақтайды. "
            "GeoScape, GS2 және Paradox бастапқы файлдары автоматты түрде өзгертілмейді."
        ),
        "save_project": "Жобаны сақтау",
        "export_las": "LAS көшірмесін экспорттау",
        "discard": "Сақтамау",
        "cancel": "Болдырмау",
        "export_title": "Өзгертілген деректерді LAS түрінде сақтау",
        "overwrite_title": "Қайта жазуды растау",
        "overwrite_text": "«{name}» файлы бар. Оны қайта жазу керек пе?",
        "export_failed": "LAS көшірмесін сақтау мүмкін болмады:\n{error}",
        "export_done_title": "LAS көшірмесі сақталды",
        "export_done": (
            "Ағымдағы қисықтар мен тақырыптар сақталды:\n{path}\n\n"
            "Пішіндер, безендіру және жобаның басқа деректері LAS құрамына кірмейді. "
            "Жобаны сақтамай бағдарламаны жабу керек пе?"
        ),
    },
    AppLanguage.EN: {
        "project": "Project",
        "well": "Well",
        "dataset": "Data",
        "source": "Source",
        "saved": "Saved",
        "modified": "Modified",
        "empty": "—",
        "format": "Format",
        "rows": "Rows",
        "curves": "Curves",
        "project_path": "Project file",
        "save_target": "Save as",
        "save_project_target": "project",
        "save_copy_target": "project or LAS copy",
        "close_title": "Unsaved data",
        "close_text": "The current working session contains unsaved changes.",
        "close_info": (
            "Saving the project preserves data, forms, and presentation. "
            "LAS export preserves only the current curves and headers. "
            "Original GeoScape, GS2, and Paradox files are never changed automatically."
        ),
        "save_project": "Save project",
        "export_las": "Export LAS copy",
        "discard": "Don't save",
        "cancel": "Cancel",
        "export_title": "Save edited data as LAS",
        "overwrite_title": "Confirm overwrite",
        "overwrite_text": "The file “{name}” already exists. Overwrite it?",
        "export_failed": "Could not save the LAS copy:\n{error}",
        "export_done_title": "LAS copy saved",
        "export_done": (
            "The current curves and headers were saved to:\n{path}\n\n"
            "Forms, presentation, and other project data are not stored in LAS. "
            "Close without saving the project?"
        ),
    },
}


def _compact(value: object, limit: int = 28) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def _safe_las_stem(value: object) -> str:
    text = str(value or "dataset").strip() or "dataset"
    forbidden = '<>:"/\\|?*'
    normalized = "".join("_" if character in forbidden else character for character in text)
    normalized = normalized.strip(" .")
    return normalized or "dataset"


class SessionInfoPanel(QFrame):
    """Compact always-visible summary of the active project and source data."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("sessionInfoPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            """
            QFrame#sessionInfoPanel {
                border: 1px solid palette(midlight);
                border-radius: 5px;
                background: palette(base);
            }
            QLabel {
                padding: 1px 3px;
            }
            QLabel#sessionStateModified {
                font-weight: 700;
                color: #b45309;
            }
            QLabel#sessionStateSaved {
                font-weight: 700;
                color: #15803d;
            }
            """
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 1, 7, 1)
        layout.setSpacing(9)
        self.project_label = self._add_label(layout, "sessionProjectLabel")
        self.well_label = self._add_label(layout, "sessionWellLabel")
        self.dataset_label = self._add_label(layout, "sessionDatasetLabel")
        self.source_label = self._add_label(layout, "sessionSourceLabel")
        layout.addStretch(1)
        self.state_label = self._add_label(layout, "sessionStateSaved")

    @staticmethod
    def _add_label(layout: QHBoxLayout, object_name: str) -> QLabel:
        label = QLabel()
        label.setObjectName(object_name)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)
        return label

    def render(self, window: QMainWindow) -> None:
        language = normalized_language(getattr(window, "language", AppLanguage.RU))
        texts = _TEXTS[language]
        controller = getattr(window, "project_controller", None)
        session = getattr(controller, "session", None) or getattr(window, "session", None)
        project = getattr(session, "project", None)
        well = getattr(session, "current_well", None)
        dataset = getattr(session, "current_dataset", None)

        project_name = getattr(project, "name", None) or texts["empty"]
        well_name = getattr(well, "name", None) or texts["empty"]
        dataset_name = getattr(dataset, "name", None) or texts["empty"]
        source_path = getattr(dataset, "source_path", None)
        parameters = getattr(dataset, "parameters", {}) or {}
        source_value = parameters.get("SOURCE_FILE") or source_path or texts["empty"]
        source_display = Path(str(source_value)).name if source_value != texts["empty"] else source_value

        self.project_label.setText(f"{texts['project']}: <b>{_compact(project_name)}</b>")
        self.well_label.setText(f"{texts['well']}: <b>{_compact(well_name)}</b>")
        self.dataset_label.setText(f"{texts['dataset']}: <b>{_compact(dataset_name)}</b>")
        self.source_label.setText(f"{texts['source']}: <b>{_compact(source_display, 34)}</b>")

        dirty = bool(getattr(session, "dirty", False))
        self.state_label.setObjectName(
            "sessionStateModified" if dirty else "sessionStateSaved"
        )
        self.state_label.setText(texts["modified"] if dirty else texts["saved"])
        self.style().unpolish(self.state_label)
        self.style().polish(self.state_label)

        source_format = parameters.get("SOURCE_FORMAT") or (
            Path(str(source_path)).suffix.lstrip(".").upper() if source_path else texts["empty"]
        )
        rows = len(getattr(dataset, "depth", ())) if dataset is not None else 0
        curves = len(getattr(dataset, "curves", {})) if dataset is not None else 0
        project_path = getattr(controller, "project_path", None)
        save_target = (
            texts["save_project_target"] if project_path else texts["save_copy_target"]
        )
        details = (
            f"{texts['project']}: {project_name}\n"
            f"{texts['well']}: {well_name}\n"
            f"{texts['dataset']}: {dataset_name}\n"
            f"{texts['source']}: {source_value}\n"
            f"{texts['format']}: {source_format}\n"
            f"{texts['rows']}: {rows}\n"
            f"{texts['curves']}: {curves}\n"
            f"{texts['project_path']}: {project_path or texts['empty']}\n"
            f"{texts['save_target']}: {save_target}"
        )
        self.setToolTip(details)
        for label in (
            self.project_label,
            self.well_label,
            self.dataset_label,
            self.source_label,
            self.state_label,
        ):
            label.setToolTip(details)


class SessionSafetyController(QObject):
    """Protect imported and edited data from silent loss when the window closes."""

    REFRESH_INTERVAL_MS = 350

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self.window: Any = window
        self.panel = SessionInfoPanel(window)
        self.window.statusBar().addPermanentWidget(self.panel, 1)
        self.window.session_info_panel = self.panel
        self.window.installEventFilter(self)
        self._timer = QTimer(self)
        self._timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def refresh(self) -> None:
        self.panel.render(self.window)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.window and event.type() == QEvent.Type.Close:
            if isinstance(event, QCloseEvent) and not self._handle_close_request():
                event.ignore()
                return True
        return False

    def _handle_close_request(self) -> bool:
        session = self._session()
        if session is None or not bool(getattr(session, "dirty", False)):
            return True
        choice = self._ask_close_choice()
        if choice is CloseChoice.CANCEL:
            return False
        if choice is CloseChoice.DISCARD:
            return True
        if choice is CloseChoice.SAVE_PROJECT:
            save = getattr(self.window, "save_project", None)
            if not callable(save):
                return False
            save()
            self.refresh()
            return not bool(getattr(self._session(), "dirty", True))
        if choice is CloseChoice.EXPORT_LAS:
            return self._export_las_before_close()
        return False

    def _session(self) -> object | None:
        controller = getattr(self.window, "project_controller", None)
        return getattr(controller, "session", None) or getattr(self.window, "session", None)

    def _ask_close_choice(self) -> CloseChoice:
        language = normalized_language(getattr(self.window, "language", AppLanguage.RU))
        texts = _TEXTS[language]
        message = QMessageBox(self.window)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle(texts["close_title"])
        message.setText(texts["close_text"])
        message.setInformativeText(texts["close_info"])
        save_button = message.addButton(
            texts["save_project"], QMessageBox.ButtonRole.AcceptRole
        )
        export_button = message.addButton(
            texts["export_las"], QMessageBox.ButtonRole.ActionRole
        )
        discard_button = message.addButton(
            texts["discard"], QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_button = message.addButton(
            texts["cancel"], QMessageBox.ButtonRole.RejectRole
        )
        dataset = getattr(self._session(), "current_dataset", None)
        export_button.setEnabled(dataset is not None)
        message.setDefaultButton(save_button)
        message.setEscapeButton(cancel_button)
        message.exec()
        clicked = message.clickedButton()
        if clicked is save_button:
            return CloseChoice.SAVE_PROJECT
        if clicked is export_button:
            return CloseChoice.EXPORT_LAS
        if clicked is discard_button:
            return CloseChoice.DISCARD
        return CloseChoice.CANCEL

    def _export_las_before_close(self) -> bool:
        session = self._session()
        dataset = getattr(session, "current_dataset", None)
        if dataset is None:
            return False
        language = normalized_language(getattr(self.window, "language", AppLanguage.RU))
        texts = _TEXTS[language]
        source_path = getattr(dataset, "source_path", None)
        if source_path is not None and Path(source_path).suffix.casefold() == ".las":
            source = Path(source_path)
            initial = source.with_name(f"{source.stem}_edited.las")
        else:
            initial = Path.cwd() / f"{_safe_las_stem(getattr(dataset, 'name', None))}_edited.las"
        filename, _ = QFileDialog.getSaveFileName(
            self.window,
            texts["export_title"],
            str(initial),
            "LAS (*.las)",
        )
        if not filename:
            return False
        target = Path(filename)
        if target.suffix.casefold() != ".las":
            target = target.with_suffix(".las")
        if target.exists():
            answer = QMessageBox.question(
                self.window,
                texts["overwrite_title"],
                texts["overwrite_text"].format(name=target.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer is not QMessageBox.StandardButton.Yes:
                return False
        exporter = getattr(self.window, "_export_current_dataset_to_path", None)
        if not callable(exporter):
            return False
        try:
            exported = Path(exporter(target))
        except (LasExportError, OSError, RuntimeError, TypeError, ValueError) as exc:
            QMessageBox.critical(
                self.window,
                texts["export_title"],
                texts["export_failed"].format(error=str(exc)),
            )
            return False
        answer = QMessageBox.question(
            self.window,
            texts["export_done_title"],
            texts["export_done"].format(path=exported),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer is QMessageBox.StandardButton.Yes


def install_session_safety(window: QMainWindow) -> SessionSafetyController:
    """Install or return the session panel and close-protection controller."""

    existing = getattr(window, "_session_safety_controller", None)
    if isinstance(existing, SessionSafetyController):
        return existing
    controller = SessionSafetyController(window)
    setattr(window, "_session_safety_controller", controller)
    return controller
