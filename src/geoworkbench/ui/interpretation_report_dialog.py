from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.printing.interpretation_report import (
    InterpretationReportError,
    build_interpretation_report,
    export_interpretation_report_pdf,
    interpretation_report_html,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage, Localizer


class InterpretationReportDialog(QDialog):
    def __init__(
        self,
        session: ProjectSession,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.language = language
        self.localizer = Localizer.create(language)
        self.report = build_interpretation_report(session)
        self.setWindowTitle(self._t("interpretation_report.title"))
        self.resize(1000, 700)
        layout = QVBoxLayout(self)
        self.preview = QTextBrowser()
        self.preview.setObjectName("interpretation-report-preview")
        self.preview.setHtml(interpretation_report_html(self.report, language))
        layout.addWidget(self.preview)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self._t("common.close"))
        self.export_button = QPushButton(self._t("interpretation_report.export"))
        self.export_button.setObjectName("interpretation-report-export")
        self.export_button.clicked.connect(self._export_pdf)
        buttons.addButton(self.export_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _export_pdf(self) -> None:
        safe_well_name = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in self.report.well_name
        ).strip("_")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._t("interpretation_report.save_title"),
            str(Path.cwd() / f"{safe_well_name or 'well'}-interpretation.pdf"),
            "PDF (*.pdf)",
        )
        if not filename:
            return
        target = Path(filename)
        if target.suffix.casefold() != ".pdf":
            target = target.with_suffix(".pdf")
        overwrite = False
        if target.exists():
            answer = QMessageBox.question(
                self,
                self._t("interpretation_report.title"),
                self._t("export.overwrite_question", name=target.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            overwrite = True
        try:
            exported = export_interpretation_report_pdf(
                self.report,
                target,
                language=self.language,
                overwrite=overwrite,
            )
        except (FileExistsError, InterpretationReportError, OSError) as exc:
            QMessageBox.critical(self, self._t("interpretation_report.title"), str(exc))
            return
        QMessageBox.information(
            self,
            self._t("interpretation_report.title"),
            self._t("interpretation_report.exported", name=exported.name),
        )
