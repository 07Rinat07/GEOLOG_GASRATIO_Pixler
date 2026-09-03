from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QFileDialog, QMenu, QMessageBox

from geoworkbench.app.context import ApplicationContext
from geoworkbench.importers.gs2 import Gs2ContainerError, extract_gs2_table
from geoworkbench.importers.gs2.metadata import channel_dictionary_for_table
from geoworkbench.importers.gs2.multipart import read_gs2_multipart
from geoworkbench.project.drilling_calculation_coordinator import (
    DrillingCalculationCoordinator,
)
from geoworkbench.project.gs2_import_coordinator import Gs2ImportCoordinator
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.drilling_calculation_dialog import DrillingCalculationDialog
from geoworkbench.ui.gs2_import_dialog import Gs2ImportDialog
from geoworkbench.ui.main_window import MainWindow as _LegacyMainWindow
from geoworkbench.ui.paradox_import_dialog import ParadoxImportDialog


class MainWindow(_LegacyMainWindow):
    """Main window with project mutations delegated to feature coordinators."""

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
        self.gs2_import_coordinator = Gs2ImportCoordinator(self._dataset_import_jobs)
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

    def open_gs2(self, source: str | Path | None = None) -> None:
        """Collect GS2 UI choices and delegate all Dataset writes/registration."""

        if source is None:
            filename, _ = QFileDialog.getOpenFileName(
                self,
                self._t("gs2.title"),
                "",
                "GeoScape II (*.gs2 *.GS2);;All files (*)",
            )
            if not filename:
                return
            selected = Path(filename)
        else:
            selected = Path(source)

        container_dialog = Gs2ImportDialog(selected, self, language=self.language)
        if container_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        member_names = container_dialog.selected_table_members
        if not member_names:
            return

        manifest = container_dialog.manifest
        metadata = container_dialog.metadata
        selected_summary = (
            next(
                (
                    table
                    for table in manifest.tables
                    if table.member_name.casefold() == member_names[0].casefold()
                ),
                None,
            )
            if manifest is not None
            else None
        )
        channel_dictionary = None
        matched_metadata_channels = 0
        matched_sensor_channels = 0
        if metadata is not None and selected_summary is not None:
            (
                channel_dictionary,
                matched_metadata_channels,
                matched_sensor_channels,
            ) = channel_dictionary_for_table(
                metadata,
                selected_summary.field_names,
                member_names[0],
            )

        result = None
        requested_action = "open"
        if len(member_names) == 1:
            member_name = member_names[0]
            try:
                with extract_gs2_table(selected, member_name) as (table_path, _manifest):
                    dialog = ParadoxImportDialog(
                        table_path,
                        self,
                        language=self.language,
                        channel_dictionary=channel_dictionary,
                    )
                    if dialog.exec() != QDialog.DialogCode.Accepted or dialog.import_result is None:
                        return
                    result = dialog.import_result
                    requested_action = dialog.requested_action
            except Gs2ContainerError as exc:
                QMessageBox.critical(self, self._t("gs2.title"), str(exc))
                return
            table_label = Path(member_name).stem
        else:
            dialog = ParadoxImportDialog(
                selected,
                self,
                language=self.language,
                table_loader=partial(
                    read_gs2_multipart,
                    member_names=member_names,
                ),
                channel_dictionary=channel_dictionary,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted or dialog.import_result is None:
                return
            result = dialog.import_result
            requested_action = dialog.requested_action
            table_label = f"{Path(member_names[0]).stem} ({len(member_names)} parts)"

        if result is None:
            return
        registration = self.gs2_import_coordinator.enrich_and_register(
            selected,
            result,
            member_names=member_names,
            table_label=table_label,
            metadata=metadata,
            matched_metadata_channels=matched_metadata_channels,
            matched_sensor_channels=matched_sensor_channels,
            review_dataset=self._review_imported_dataset,
        )
        if registration.review_skipped:
            self.statusBar().showMessage(
                self._t("import_review.cancelled_status", file=selected.name)
            )
            return
        if registration.result is None:
            QMessageBox.critical(self, self._t("gs2.title"), registration.error)
            return

        self._refresh_tree()
        self._show_current_dataset()
        self._update_title()
        self.statusBar().showMessage(
            self._t(
                "gs2.imported",
                file=selected.name,
                table=table_label,
                rows=registration.result.table.rows_read,
            )
        )
        self._dispatch_registered_import_action(requested_action)

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
