from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.help_content import (
    help_center_title,
    help_sections,
    normalized_language,
)
from geoworkbench.ui.help_pdf_layout_content import append_pdf_layout_help


class HelpCenterDialog(QDialog):
    """Single in-application location for user documentation and workflows."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        section: str = "overview",
    ) -> None:
        super().__init__(parent)
        self.language = normalized_language(language)
        self._requested_section = section
        self.setObjectName("helpCenterDialog")
        self.setModal(False)
        self.resize(1_020, 760)

        layout = QVBoxLayout(self)
        self.sections = QTabWidget(self)
        self.sections.setObjectName("help-center-tabs")
        self.sections.setDocumentMode(True)
        self.sections.setUsesScrollButtons(True)
        layout.addWidget(self.sections, 1)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._rebuild()

    def set_language(self, language: AppLanguage | str) -> None:
        selected = normalized_language(language)
        if selected is self.language:
            return
        current = self.current_section()
        self.language = selected
        self._requested_section = current
        self._rebuild()

    def select_section(self, section: str) -> None:
        self._requested_section = section
        for index in range(self.sections.count()):
            widget = self.sections.widget(index)
            if widget is not None and widget.property("helpSectionKey") == section:
                self.sections.setCurrentIndex(index)
                return

    def current_section(self) -> str:
        widget = self.sections.currentWidget()
        if widget is None:
            return "overview"
        value = widget.property("helpSectionKey")
        return str(value) if value else "overview"

    def _rebuild(self) -> None:
        self.setWindowTitle(help_center_title(self.language))
        close_button = self.buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.setText(
                {
                    AppLanguage.RU: "Закрыть",
                    AppLanguage.KK: "Жабу",
                    AppLanguage.EN: "Close",
                }[self.language]
            )

        self.sections.clear()
        requested_index = 0
        for index, section in enumerate(help_sections(self.language)):
            browser = QTextBrowser(self.sections)
            browser.setObjectName(f"help-section-{section.key}")
            browser.setProperty("helpSectionKey", section.key)
            browser.setOpenExternalLinks(True)
            html = section.html
            if section.key in {"printing", "interpretation"}:
                html = append_pdf_layout_help(html, self.language)
            browser.setHtml(html)
            self.sections.addTab(browser, section.title)
            if section.key == self._requested_section:
                requested_index = index
        self.sections.setCurrentIndex(requested_index)
