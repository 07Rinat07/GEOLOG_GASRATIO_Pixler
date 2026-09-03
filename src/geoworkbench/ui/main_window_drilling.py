from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QMenu, QMessageBox

from geoworkbench.app.context import ApplicationContext
from geoworkbench.project.drilling_calculation_coordinator import (
    DrillingCalculationCoordinator,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.drilling_calculation_dialog import DrillingCalculationDialog
from geoworkbench.ui.main_window import MainWindow as _LegacyMainWindow


class MainWindow(_LegacyMainWindow):
    """Main window with one shared normalized-gas and DEXP calculation command."""

    def __init__(
        self,
        *args,
        application_context: ApplicationContext | None = None,
        **kwargs,
    ) -> None:
        self.application_context = application_context
        super().__init__(*args, **kwargs)
        self.drilling_calculation_coordinator = DrillingCalculationCoordinator(
            self.interpretation_calculation_controller
        )
        self._install_drilling_calculation_action()

    def _install_drilling_calculation_action(self) -> None:
        calculations_menu = self._calculations_menu()
        if calculations_menu is None:
            raise RuntimeError("Не найдено меню расчётов")
        self.drilling_calculation_action = QAction(self)
        self.drilling_calculation_action.setObjectName("drillingCalculationAction")
        self.drilling_calculation_action.triggered.connect(
            self.show_drilling_calculation_dialog
        )
        self._retranslate_drilling_calculation_action()
        before = getattr(self, "formula_action", None)
        if isinstance(before, QAction):
            calculations_menu.insertAction(before, self.drilling_calculation_action)
        else:
            calculations_menu.addAction(self.drilling_calculation_action)

    def _calculations_menu(self) -> QMenu | None:
        for action in self.menuBar().actions():
            menu = action.menu()
            if (
                isinstance(menu, QMenu)
                and action.property("i18n_key") == "menu.calculations"
            ):
                return menu
        return None

    def show_drilling_calculation_dialog(self) -> None:
        if self.session.current_dataset is None:
            QMessageBox.information(
                self,
                self._drilling_text(
                    "Нормализованный газ и DEXP",
                    "Нормаланған газ және DEXP",
                    "Normalized gas and DEXP",
                ),
                self._drilling_text(
                    "Сначала выберите набор данных.",
                    "Алдымен деректер жинағын таңдаңыз.",
                    "Select a dataset first.",
                ),
            )
            return

        workspace = self.interpretation_report_workspace
        reference = workspace._normalized_reference()
        density = workspace.normal_density.value()
        dialog = DrillingCalculationDialog(
            self.interpretation_calculation_controller,
            self,
            language=self.language,
            normalized_reference=reference,
            normal_mud_density_ppg=density if density > 0.0 else None,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        request = dialog.request()
        outcome = self.drilling_calculation_coordinator.apply_and_calculate(
            plan=request.plan,
            normalized_reference=request.normalized_reference,
            normal_mud_density_ppg=request.normal_mud_density_ppg,
            normalized_gas_mode=workspace._current_normalized_gas_mode(),
        )

        workspace.rop_reference.setValue(request.normalized_reference.rop_ref_fph)
        workspace.bit_reference.setValue(request.normalized_reference.bit_ref_in)
        workspace.flow_reference.setValue(request.normalized_reference.flow_ref_gpm)
        workspace.gas_efficiency.setValue(
            request.normalized_reference.gas_system_efficiency
        )
        workspace.normal_density.setValue(request.normal_mud_density_ppg or 0.0)

        self._after_interpretation_calculation(outcome.result)
        workspace.refresh()
        workspace._update_drilling_input_status()
        if outcome.visible_curves:
            self.tabs.setCurrentWidget(self.tablet_view)
        if outcome.result.issues:
            QMessageBox.warning(
                self,
                self._drilling_text(
                    "Результат расчёта",
                    "Есептеу нәтижесі",
                    "Calculation result",
                ),
                "\n".join(f"• {issue.message}" for issue in outcome.result.issues),
            )

    def change_language(self, language: AppLanguage) -> None:
        super().change_language(language)
        if hasattr(self, "drilling_calculation_action"):
            self._retranslate_drilling_calculation_action()

    def _retranslate_drilling_calculation_action(self) -> None:
        text = self._drilling_text(
            "Нормализованный газ и DEXP…",
            "Нормаланған газ және DEXP…",
            "Normalized gas and DEXP…",
        )
        tooltip = self._drilling_text(
            "Настроить ROP, FLOW, RPM, WOB, плотность и секции фактического BIT, затем "
            "рассчитать нормализованный газ и DEXP.",
            "ROP, FLOW, RPM, WOB, тығыздық және нақты BIT секцияларын баптап, нормаланған "
            "газ бен DEXP есептеу.",
            "Configure ROP, FLOW, RPM, WOB, mud density, and actual BIT sections, then "
            "calculate normalized gas and DEXP.",
        )
        self.drilling_calculation_action.setText(text)
        self.drilling_calculation_action.setToolTip(tooltip)
        self.drilling_calculation_action.setStatusTip(tooltip)

    def _drilling_text(self, ru: str, kk: str, en: str) -> str:
        return {AppLanguage.RU: ru, AppLanguage.KK: kk, AppLanguage.EN: en}[
            self.language
        ]


__all__ = ["MainWindow"]
