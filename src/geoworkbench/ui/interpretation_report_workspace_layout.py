from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from geoworkbench.ui.interpretation_report_workspace_responsive import (
    InterpretationReportWorkspace as _ResponsiveInterpretationReportWorkspace,
)


class InterpretationReportWorkspace(_ResponsiveInterpretationReportWorkspace):
    """Final responsive layout implementation used by the application."""

    def _rebuild_dexp_panel(self) -> None:
        panel = self.dexp_quality_panel.layout()
        if not isinstance(panel, QHBoxLayout):
            raise RuntimeError("Не найден layout блока качества DEXP")
        while panel.count():
            panel.takeAt(0)
        panel.setContentsMargins(0, 0, 0, 0)
        panel.setSpacing(0)
        self.dexp_quality_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        content = QWidget()
        content.setObjectName("dexp-quality-content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 13, 16, 13)
        content_layout.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(self.dexp_quality_title)
        header.addStretch(1)
        header.addWidget(self.dexp_details_button)
        content_layout.addLayout(header)
        content_layout.addWidget(self.dexp_quality_summary)
        content_layout.addWidget(self.dexp_quality_progress)
        content_layout.addWidget(self.dexp_quality_reasons)
        panel.addWidget(content)

    def _retranslate_responsive_controls(self) -> None:
        super()._retranslate_responsive_controls()
        self.recalculate_all_button.setText(
            self._text(
                "Пересчитать все доступные кривые и открыть планшет",
                "Барлық қолжетімді қисықтарды қайта есептеп, планшетті ашу",
                "Recalculate all available curves and open tablet",
            )
        )
        self.refresh_chart_report_button.setText(
            self._text(
                "Обновить отчёт с графиками",
                "Графиктері бар есепті жаңарту",
                "Refresh report with charts",
            )
        )


__all__ = ["InterpretationReportWorkspace"]
