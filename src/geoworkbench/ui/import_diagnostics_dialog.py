from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.services.import_diagnostics import ImportDiagnosticReport
from geoworkbench.services.localization import AppLanguage, Localizer


class ImportDiagnosticsDialog(QDialog):
    """Display and export a complete actionable import diagnostic report."""

    def __init__(
        self,
        report: ImportDiagnosticReport,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.report = report
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self._t("import_diagnostics.title"))
        self.resize(920, 620)

        layout = QVBoxLayout(self)
        summary = QLabel(
            self._t(
                "import_diagnostics.summary",
                errors=report.error_count,
                warnings=report.warning_count,
            )
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)

        self.report_text = QPlainTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setPlainText(self._format_report())
        layout.addWidget(self.report_text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        copy_button = QPushButton(self._t("import_diagnostics.copy"))
        save_button = QPushButton(self._t("import_diagnostics.save"))
        buttons.addButton(copy_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(save_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        copy_button.clicked.connect(self._copy_report)
        save_button.clicked.connect(self._save_report)
        layout.addWidget(buttons)

    def _format_report(self) -> str:
        lines: list[str] = []
        for index, item in enumerate(self.report.diagnostics, start=1):
            severity = self.localizer.catalog.get(
                f"import_diagnostics.severity.{item.severity.value}",
                item.severity.value.upper(),
            )
            stage = self.localizer.catalog.get(
                f"import_diagnostics.stage.{item.stage.value}",
                item.stage.value,
            )
            summary = self.localizer.catalog.get(
                f"import_diagnostics.code.{item.code}.summary",
                item.summary,
            )
            action = self.localizer.catalog.get(
                f"import_diagnostics.code.{item.code}.action",
                item.suggested_action,
            )
            lines.extend(
                (
                    f"[{index}] {severity} / {stage} / {item.code}",
                    f"{self._t('import_diagnostics.source')}: {item.source}",
                    f"{self._t('import_diagnostics.problem')}: {summary}",
                    f"{self._t('import_diagnostics.details')}: {item.details}",
                    f"{self._t('import_diagnostics.action')}: {action}",
                )
            )
            if item.exception_type:
                lines.append(
                    f"{self._t('import_diagnostics.exception')}: {item.exception_type}"
                )
            for key, value in item.context:
                lines.append(f"{key}: {value}")
            if item.technical_details:
                lines.extend(
                    (
                        self._t("import_diagnostics.technical"),
                        item.technical_details.rstrip(),
                    )
                )
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _copy_report(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self.report_text.toPlainText())
        QMessageBox.information(
            self,
            self._t("import_diagnostics.title"),
            self._t("import_diagnostics.copied"),
        )

    def _save_report(self) -> None:
        default_root = Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DocumentsLocation
            )
        )
        target, _ = QFileDialog.getSaveFileName(
            self,
            self._t("import_diagnostics.save"),
            str(default_root / "geolog_import_diagnostics.txt"),
            "Text (*.txt)",
        )
        if not target:
            return
        try:
            Path(target).write_text(self.report_text.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(
                self,
                self._t("import_diagnostics.title"),
                self._t("import_diagnostics.save_failed", error=str(exc)),
            )
            return
        QMessageBox.information(
            self,
            self._t("import_diagnostics.title"),
            self._t("import_diagnostics.saved", file=target),
        )
