from __future__ import annotations

from enum import Enum

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from geoworkbench.services.localization import AppLanguage


class SkfImportMode(str, Enum):
    FORM_AND_HEADER = "form_and_header"
    FORM_ONLY = "form_only"
    HEADER_ONLY = "header_only"


class SkfImportOptionsDialog(QDialog):
    """Ask explicitly how a vendor SKF document should be installed."""

    def __init__(self, parent=None, *, language: AppLanguage = AppLanguage.RU) -> None:
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(
            {
                AppLanguage.RU: "Как импортировать SKF",
                AppLanguage.KK: "SKF қалай импортталады",
                AppLanguage.EN: "How to import SKF",
            }[language]
        )
        self.setMinimumWidth(560)

        intro = QLabel(
            {
                AppLanguage.RU: (
                    "SKF может содержать готовую планшетную форму, печатную шапку и полную "
                    "Masterlog-композицию. Выберите назначение явно — программа не будет угадывать."
                ),
                AppLanguage.KK: (
                    "SKF дайын планшет пішінін, баспа тақырыбын және толық Masterlog құрамын "
                    "қамтуы мүмкін. Қолдану тәсілін нақты таңдаңыз."
                ),
                AppLanguage.EN: (
                    "An SKF may contain a ready tablet form, a reusable print header and a full "
                    "Masterlog composition. Choose the intended import explicitly."
                ),
            }[language]
        )
        intro.setWordWrap(True)

        self.group = QButtonGroup(self)
        options = (
            (
                SkfImportMode.FORM_AND_HEADER,
                {
                    AppLanguage.RU: "Форма + шапка + полная Masterlog-композиция",
                    AppLanguage.KK: "Пішін + тақырып + толық Masterlog құрамы",
                    AppLanguage.EN: "Form + header + full Masterlog composition",
                }[language],
                {
                    AppLanguage.RU: "Рекомендуется для готовых решений поставщика.",
                    AppLanguage.KK: "Жеткізушінің дайын шешімдері үшін ұсынылады.",
                    AppLanguage.EN: "Recommended for complete vendor solutions.",
                }[language],
            ),
            (
                SkfImportMode.FORM_ONLY,
                {
                    AppLanguage.RU: "Только форма планшета и колонки",
                    AppLanguage.KK: "Тек планшет пішіні мен бағандар",
                    AppLanguage.EN: "Tablet form and columns only",
                }[language],
                {
                    AppLanguage.RU: "Шапка и Masterlog-шаблон не добавляются.",
                    AppLanguage.KK: "Тақырып пен Masterlog үлгісі қосылмайды.",
                    AppLanguage.EN: "Does not add a header or Masterlog template.",
                }[language],
            ),
            (
                SkfImportMode.HEADER_ONLY,
                {
                    AppLanguage.RU: "Только печатная шапка в каталог",
                    AppLanguage.KK: "Тек баспа тақырыбын каталогқа",
                    AppLanguage.EN: "Reusable print header only",
                }[language],
                {
                    AppLanguage.RU: "Форма планшета и колонки не создаются.",
                    AppLanguage.KK: "Планшет пішіні мен бағандар жасалмайды.",
                    AppLanguage.EN: "Does not create a tablet form or columns.",
                }[language],
            ),
        )

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        for index, (mode, title, description) in enumerate(options):
            radio = QRadioButton(title)
            radio.setProperty("skf_mode", mode.value)
            radio.setToolTip(description)
            radio.setChecked(index == 0)
            self.group.addButton(radio)
            layout.addWidget(radio)
            hint = QLabel(description)
            hint.setWordWrap(True)
            hint.setStyleSheet("margin-left:24px; color:#64748b;")
            layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def mode(self) -> SkfImportMode:
        checked = self.group.checkedButton()
        raw = checked.property("skf_mode") if checked is not None else None
        try:
            return SkfImportMode(str(raw))
        except ValueError:
            return SkfImportMode.FORM_AND_HEADER
