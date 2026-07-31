from __future__ import annotations

from PySide6.QtGui import QPalette

from geoworkbench.ui.interpretation_report_workspace_polish import (
    InterpretationReportWorkspace as _PolishedInterpretationReportWorkspace,
)


class InterpretationReportWorkspace(_PolishedInterpretationReportWorkspace):
    """Polished workspace that preserves established UI contracts."""

    def _apply_polished_theme(self) -> None:
        super()._apply_polished_theme()
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        workspace_background = "#15191f" if dark else "#f4f7fb"
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QWidget#interpretation-report-workspace {{
                background: {workspace_background};
            }}
            QWidget#interpretation-report-workspace QComboBox QAbstractItemView {{
                background: palette(base);
            }}
            """
        )

    def _retranslate_polish_controls(self) -> None:
        super()._retranslate_polish_controls()
        self.recalculate_all_button.setText(
            self._text(
                "Пересчитать все доступные кривые и открыть планшет",
                "Барлық қолжетімді қисықтарды қайта есептеп, планшетті ашу",
                "Recalculate all available curves and open tablet",
            )
        )
        self.configure_drilling_inputs_button.setText(
            self._text(
                "Настроить BIT и входные данные…",
                "BIT және кіріс деректерін баптау…",
                "Configure BIT and inputs…",
            )
        )


__all__ = ["InterpretationReportWorkspace"]
