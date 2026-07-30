from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.services.drilling_input_plan import InputSourceMode
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.drilling_calculation_dialog import DrillingCalculationDialog
from geoworkbench.ui.interpretation_report_workspace_final import (
    InterpretationReportWorkspace as _FinalInterpretationReportWorkspace,
)


class InterpretationReportWorkspace(_FinalInterpretationReportWorkspace):
    """Interpretation workspace sharing one drilling-input plan with the calculations menu."""

    def __init__(
        self,
        controller: InterpretationCalculationController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(controller, parent, language=language)
        panel = self.normalized_gas_panel.layout()
        if not isinstance(panel, QVBoxLayout):
            raise RuntimeError("Не найден layout блока нормализованного газа")

        self.drilling_input_status = QLabel()
        self.drilling_input_status.setObjectName("drilling-input-plan-status")
        self.drilling_input_status.setWordWrap(True)
        panel.addWidget(self.drilling_input_status)

        action_row = QHBoxLayout()
        self.configure_drilling_inputs_button = QPushButton()
        self.configure_drilling_inputs_button.setObjectName("configure-drilling-inputs")
        self.configure_drilling_inputs_button.clicked.connect(
            self.configure_drilling_inputs_and_calculate
        )
        action_row.addWidget(self.configure_drilling_inputs_button)
        action_row.addStretch(1)
        panel.addLayout(action_row)
        self._retranslate_drilling_controls()
        self._update_drilling_input_status()

    def configure_drilling_inputs_and_calculate(self) -> None:
        dialog = DrillingCalculationDialog(
            self.controller,
            self,
            language=self.language,
            normalized_reference=self._normalized_reference(),
            normal_mud_density_ppg=(
                self.normal_density.value() if self.normal_density.value() > 0.0 else None
            ),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        request = dialog.request()
        self.controller.set_drilling_input_plan(request.plan)
        self.rop_reference.setValue(request.normalized_reference.rop_ref_fph)
        self.bit_reference.setValue(request.normalized_reference.bit_ref_in)
        self.flow_reference.setValue(request.normalized_reference.flow_ref_gpm)
        self.gas_efficiency.setValue(request.normalized_reference.gas_system_efficiency)
        self.normal_density.setValue(request.normal_mud_density_ppg or 0.0)

        result = self.controller.calculate_standard_curves(
            normal_mud_density_ppg=request.normal_mud_density_ppg,
            normalized_gas_reference=request.normalized_reference,
            normalized_gas_mode=self._current_normalized_gas_mode(),
        )
        self.calculation_completed.emit(result)
        self.refresh()
        self._update_drilling_input_status()
        self._set_combined_result_status(result)
        visible = tuple(
            dict.fromkeys(
                (
                    *result.track_curves.get("gas_ratio_pixler", ()),
                    *result.track_curves.get("normalized_gas", ()),
                    *result.track_curves.get("dexp", ()),
                )
            )
        )
        if visible:
            self._open_tablet()
        if result.issues:
            self._show_result_warning(result)

    def set_language(self, language: AppLanguage) -> None:
        super().set_language(language)
        if hasattr(self, "configure_drilling_inputs_button"):
            self._retranslate_drilling_controls()
            self._update_drilling_input_status()

    def _retranslate_drilling_controls(self) -> None:
        self.configure_drilling_inputs_button.setText(
            self._text(
                "Настроить секции BIT и входы DEXP…",
                "BIT секциялары мен DEXP кірістерін баптау…",
                "Configure BIT sections and DEXP inputs…",
            )
        )
        self.configure_drilling_inputs_button.setToolTip(
            self._text(
                "Выбрать кривые ROP/FLOW/RPM/WOB, задать фактический диаметр по секциям "
                "и выполнить общий расчёт.",
                "ROP/FLOW/RPM/WOB қисықтарын таңдап, нақты диаметрді секциялармен беріп, "
                "жалпы есептеуді орындау.",
                "Select ROP/FLOW/RPM/WOB curves, define actual hole size by section, and "
                "run the shared calculation.",
            )
        )

    def _update_drilling_input_status(self) -> None:
        plan = self.controller.drilling_input_plan
        if plan.bit.mode is InputSourceMode.SECTIONS:
            bit_text = self._text(
                f"BIT: таблица секций, строк {len(plan.bit_sections)}",
                f"BIT: секциялар кестесі, жол саны {len(plan.bit_sections)}",
                f"BIT: section table, {len(plan.bit_sections)} rows",
            )
        elif plan.bit.mode is InputSourceMode.CONSTANT:
            bit_text = self._text(
                f"BIT: постоянное {plan.bit.value:g} {plan.bit.unit}",
                f"BIT: тұрақты {plan.bit.value:g} {plan.bit.unit}",
                f"BIT: constant {plan.bit.value:g} {plan.bit.unit}",
            )
        elif plan.bit.mode is InputSourceMode.CURVE:
            bit_text = self._text(
                "BIT: явно выбранная кривая",
                "BIT: нақты таңдалған қисық",
                "BIT: explicitly selected curve",
            )
        else:
            bit_text = self._text(
                "BIT: автоматический поиск кривой",
                "BIT: қисықты автоматты іздеу",
                "BIT: automatic curve search",
            )
        self.drilling_input_status.setText(
            self._text(
                "Общие входы нормализованного газа и DEXP — ",
                "Нормаланған газ бен DEXP ортақ кірістері — ",
                "Shared normalized-gas and DEXP inputs — ",
            )
            + bit_text
        )


__all__ = ["InterpretationReportWorkspace"]
