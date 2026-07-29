from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

_INSTALL_COMMAND = 'python -m pip install --upgrade "PyMuPDF>=1.28,<2" "Pillow>=12.3,<13"'


def _is_optional_dependency_error(error: ModuleNotFoundError) -> bool:
    name = error.name or ""
    return name == "pymupdf" or name == "fitz" or name == "PIL" or name.startswith("PIL.")


class FileWorkspaceWidget(QWidget):
    """Load the full Files workspace without making it a startup dependency.

    Existing installations may update the application before their virtual
    environment receives newly introduced PDF/image packages. In that state the
    main geological workspace must still start. The full widget is imported only
    when this tab is constructed; a local explanatory placeholder is used when
    PyMuPDF or Pillow is absent.
    """

    def __new__(
        cls,
        parent: QWidget | None = None,
        *,
        language: str = "ru",
    ) -> FileWorkspaceWidget:
        try:
            from geoworkbench.ui.file_workspace_full_widget import (
                FileWorkspaceWidget as FullFileWorkspaceWidget,
            )
        except ModuleNotFoundError as error:
            if not _is_optional_dependency_error(error):
                raise
            instance = super().__new__(cls)
            instance._missing_dependency = error.name or "неизвестный модуль"
            return instance
        return cast(FileWorkspaceWidget, FullFileWorkspaceWidget(parent, language=language))

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: str = "ru",
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.setObjectName("fileWorkspaceDependencyFallback")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.addStretch(1)

        title = QLabel(self._text("title"), self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)

        message = QLabel(
            self._text("message").format(module=self._missing_dependency),
            self,
        )
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setWordWrap(True)
        message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(message)

        command = QLabel(f"<code>{_INSTALL_COMMAND}</code>", self)
        command.setAlignment(Qt.AlignmentFlag.AlignCenter)
        command.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        command.setWordWrap(True)
        layout.addWidget(command)

        copy_button = QPushButton(self._text("copy"), self)
        copy_button.clicked.connect(self._copy_install_command)
        layout.addWidget(copy_button, alignment=Qt.AlignmentFlag.AlignCenter)

        note = QLabel(self._text("note"), self)
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)

    @staticmethod
    def tab_title(language: str) -> str:
        return {
            "ru": "Файлы / PDF / Калькулятор",
            "kk": "Файлдар / PDF / Калькулятор",
            "en": "Files / PDF / Calculator",
        }.get(language, "Файлы / PDF / Калькулятор")

    def _copy_install_command(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(_INSTALL_COMMAND)

    def _text(self, key: str) -> str:
        texts = {
            "ru": {
                "title": "Компоненты PDF и изображений не установлены",
                "message": (
                    "Основное приложение продолжает работать. Для вкладки «Файлы / PDF / "
                    "Калькулятор» отсутствует модуль {module}. Выполните команду в активном "
                    "виртуальном окружении:"
                ),
                "copy": "Копировать команду",
                "note": "После установки перезапустите приложение.",
            },
            "kk": {
                "title": "PDF және кескін компоненттері орнатылмаған",
                "message": (
                    "Негізгі қолданба жұмысын жалғастырады. «Файлдар / PDF / Калькулятор» "
                    "қойындысына {module} модулі жетіспейді. Белсенді виртуалды ортада пәрменді "
                    "орындаңыз:"
                ),
                "copy": "Пәрменді көшіру",
                "note": "Орнатудан кейін қолданбаны қайта іске қосыңыз.",
            },
            "en": {
                "title": "PDF and image components are not installed",
                "message": (
                    "The main application remains available. The Files / PDF / Calculator tab is "
                    "missing module {module}. Run this command in the active virtual environment:"
                ),
                "copy": "Copy command",
                "note": "Restart the application after installation.",
            },
        }
        language = self.language if self.language in texts else "ru"
        return texts[language][key]
