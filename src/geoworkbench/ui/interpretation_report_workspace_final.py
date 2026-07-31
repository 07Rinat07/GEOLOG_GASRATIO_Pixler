from __future__ import annotations

from geoworkbench.data.hydrocarbon_interpretation_export import (
    HydrocarbonInterpretationExportError,
)
from geoworkbench.printing.hydrocarbon_interpretation_chart_front import (
    hydrocarbon_interpretation_html_with_front_chart,
)
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
        self.xlsx_button.setText(
            self._text(
                "Excel — сводная интерпретация (.xlsx)",
                "Excel — жиынтық интерпретация (.xlsx)",
                "Excel — consolidated interpretation (.xlsx)",
            )
        )
        self.xlsx_button.setToolTip(
            self._text(
                "Создаёт один основной лист с УВ-интервалами, интерпретацией, фоном, "
                "минимумом, средним, медианой и максимумом газа. Исходные данные "
                "сохраняются на отдельном скрытом листе для проверки.",
                "Көмірсутек аралықтары, интерпретация және газдың фондық, ең аз, орташа, "
                "медианалық және ең көп мәндері бар бір негізгі парақ жасайды. Бастапқы "
                "деректер тексеру үшін бөлек жасырын парақта сақталады.",
                "Creates one main sheet with hydrocarbon intervals, interpretation, and gas "
                "background/minimum/mean/median/maximum. Source data are retained on a "
                "separate hidden audit sheet.",
            )
        )

    def _apply_chart_preview(self) -> None:
        dataset = self.controller.session.current_dataset
        if self.report is None or dataset is None or self._is_mixture_mode():
            return
        self.preview.setHtml(
            hydrocarbon_interpretation_html_with_front_chart(
                self.report,
                dataset,
                self.language,
            )
        )

    def _export_xlsx(self) -> None:
        report = self._require_report()
        if report is None:
            return
        dataset = self.controller.session.current_dataset
        if dataset is None:
            return
        target = self._choose_target(".xlsx", "Excel (*.xlsx)")
        if target is None:
            return
        try:
            from geoworkbench.data.hydrocarbon_interpretation_export_readable import (
                export_readable_hydrocarbon_interpretation_xlsx,
            )

            exported = export_readable_hydrocarbon_interpretation_xlsx(
                report,
                dataset,
                target,
                overwrite=target.exists(),
            )
        except (OSError, FileExistsError, HydrocarbonInterpretationExportError) as exc:
            self._show_export_error(exc)
            return
        self._show_export_success(exported)


__all__ = ["InterpretationReportWorkspace"]
