from __future__ import annotations

from geoworkbench.ui.interpretation_report_workspace_expert import (
    InterpretationReportWorkspace as _ExpertInterpretationReportWorkspace,
)


class InterpretationReportWorkspace(_ExpertInterpretationReportWorkspace):
    """Final compatibility layer for the chart-enabled interpretation workspace."""

    def _retranslate_expert_controls(self) -> None:
        super()._retranslate_expert_controls()
        self.calculate_normalized_gas_button.setText(
            self._text(
                "Рассчитать локальный нормализованный газ",
                "Жергілікті нормаланған газды есептеу",
                "Calculate local normalized gas",
            )
        )
        self.show_normalized_gas_button.setText(
            self._text(
                "Показать кривые нормализованного газа на планшете",
                "Нормаланған газ қисықтарын планшетте көрсету",
                "Show normalized-gas curves on tablet",
            )
        )


__all__ = ["InterpretationReportWorkspace"]
