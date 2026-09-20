from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QFileDialog, QMenu, QMessageBox

from geoworkbench.app.context import ApplicationContext
from geoworkbench.data.late_analysis_adapter import (
    LateAnalysisImportError,
    load_late_analysis_source,
)
from geoworkbench.importers.gs2 import Gs2ContainerError, extract_gs2_table
from geoworkbench.importers.gs2.metadata import channel_dictionary_for_table
from geoworkbench.importers.gs2.multipart import read_gs2_multipart
from geoworkbench.project.annotation_schema import (
    annotation_from_canvas,
    annotation_matches_scope,
    annotation_scope_id_for_session,
    is_annotation_object,
)
from geoworkbench.project.canvas_object_transfer_controller import (
    CanvasObjectTransferController,
)
from geoworkbench.project.canvas_object_transfer_workflow import (
    CanvasObjectTransferWorkflow,
)
from geoworkbench.project.drilling_calculation_coordinator import (
    DrillingCalculationCoordinator,
)
from geoworkbench.project.gs2_import_coordinator import Gs2ImportCoordinator
from geoworkbench.project.interpretation_feature_coordinator import (
    InterpretationFeatureCoordinator,
)
from geoworkbench.project.well_analysis_update_controller import (
    WellAnalysisUpdateController,
)
from geoworkbench.project.well_analysis_update_workflow import (
    WellAnalysisUpdateWorkflow,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.canvas_object_transfer_dialog import CanvasObjectTransferDialog
from geoworkbench.ui.drilling_calculation_dialog import DrillingCalculationDialog
from geoworkbench.ui.gs2_import_dialog import Gs2ImportDialog
from geoworkbench.ui.late_analysis_review_dialog import LateAnalysisReviewDialog
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
        # Base initialization wires Qt signals that resolve methods dynamically.
        # Keep a sentinel so an unlikely initialization-time callback can fall back
        # to the legacy implementation until all project controllers exist.
        self.interpretation_feature_coordinator: InterpretationFeatureCoordinator | None = None
        super().__init__(
            *args,
            application_context=application_context,
            **kwargs,
        )
        self.drilling_calculation_coordinator = DrillingCalculationCoordinator(
            self.interpretation_calculation_controller
        )
        self.gs2_import_coordinator = Gs2ImportCoordinator(self._dataset_import_jobs)
        self.interpretation_feature_coordinator = InterpretationFeatureCoordinator(
            self.session,
            self.interpretation_controller,
            self.tablet_controller,
        )
        self._install_drilling_calculation_action()
        self._install_late_analysis_action()
        self._install_canvas_object_transfer_action()

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

    def _install_late_analysis_action(self) -> None:
        file_menu = self._menu_by_i18n_key("menu.file")
        if file_menu is None:
            raise RuntimeError("Не найдено меню файла")
        self.late_analysis_import_action = QAction(self)
        self.late_analysis_import_action.setObjectName("lateAnalysisImportAction")
        self.late_analysis_import_action.triggered.connect(
            lambda _checked=False: self.show_late_analysis_import()
        )
        self._retranslate_late_analysis_action()
        before = getattr(self, "open_data_action", None)
        if isinstance(before, QAction):
            file_menu.insertAction(before, self.late_analysis_import_action)
        else:
            file_menu.addAction(self.late_analysis_import_action)

    def _install_canvas_object_transfer_action(self) -> None:
        file_menu = self._menu_by_i18n_key("menu.file")
        if file_menu is None:
            raise RuntimeError("Не найдено меню файла")
        self.canvas_object_transfer_action = QAction(self)
        self.canvas_object_transfer_action.setObjectName("canvasObjectTransferAction")
        self.canvas_object_transfer_action.triggered.connect(
            lambda _checked=False: self.show_canvas_object_transfer()
        )
        self._retranslate_canvas_object_transfer_action()
        before = getattr(self, "open_data_action", None)
        if isinstance(before, QAction):
            file_menu.insertAction(before, self.canvas_object_transfer_action)
        else:
            file_menu.addAction(self.canvas_object_transfer_action)

    def _menu_by_i18n_key(self, key: str) -> QMenu | None:
        for action in self.menuBar().actions():
            menu = action.menu()
            if isinstance(menu, QMenu) and action.property("i18n_key") == key:
                return menu
        return None

    def _calculations_menu(self) -> QMenu | None:
        return self._menu_by_i18n_key("menu.calculations")

    def show_late_analysis_import(self, source: str | Path | None = None) -> None:
        well = self.session.current_well
        if well is None:
            QMessageBox.information(
                self,
                self._late_analysis_text(
                    "Поздние анализы",
                    "Кейінгі талдаулар",
                    "Late analyses",
                ),
                self._late_analysis_text(
                    "Сначала выберите скважину.",
                    "Алдымен ұңғыманы таңдаңыз.",
                    "Select a well first.",
                ),
            )
            return
        if self.project_path is None:
            QMessageBox.information(
                self,
                self._late_analysis_text(
                    "Поздние анализы",
                    "Кейінгі талдаулар",
                    "Late analyses",
                ),
                self._late_analysis_text(
                    "Сначала сохраните проект: подтверждённые анализы должны быть "
                    "сразу записаны в файл проекта.",
                    "Алдымен жобаны сақтаңыз: расталған талдаулар жоба файлына "
                    "бірден жазылуы тиіс.",
                    "Save the project first: confirmed analyses must be persisted "
                    "to the project file immediately.",
                ),
            )
            return

        if source is None:
            filename, _ = QFileDialog.getOpenFileName(
                self,
                self._late_analysis_text(
                    "Импорт поздних анализов",
                    "Кейінгі талдауларды импорттау",
                    "Import late analyses",
                ),
                "",
                self._late_analysis_text(
                    "Поздние анализы (*.csv *.txt *.xlsx *.xlsm);;Все файлы (*)",
                    "Кейінгі талдаулар (*.csv *.txt *.xlsx *.xlsm);;Барлық файлдар (*)",
                    "Late analyses (*.csv *.txt *.xlsx *.xlsm);;All files (*)",
                ),
            )
            if not filename:
                return
            selected = Path(filename)
        else:
            selected = Path(source)

        try:
            imported = load_late_analysis_source(selected)
        except (LateAnalysisImportError, OSError) as exc:
            QMessageBox.warning(
                self,
                self._late_analysis_text(
                    "Импорт поздних анализов",
                    "Кейінгі талдауларды импорттау",
                    "Import late analyses",
                ),
                str(exc),
            )
            return

        revision_before = well.content_revision
        history_count_before = len(well.analysis_update_history)
        controller = WellAnalysisUpdateController(self.session)
        workflow = WellAnalysisUpdateWorkflow(
            self.session,
            controller,
            self.project_controller,
        )
        dialog = LateAnalysisReviewDialog(
            workflow,
            imported.source_samples,
            source_name=imported.source_name,
            source_sha256=imported.source_sha256,
            language=self.language,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        current_well = self.session.current_well
        changed = (
            current_well is well
            and well.content_revision > revision_before
            and len(well.analysis_update_history) > history_count_before
        )
        if not changed:
            self.statusBar().showMessage(
                self._late_analysis_text(
                    "Поздние анализы: изменения не выбраны.",
                    "Кейінгі талдаулар: өзгерістер таңдалмады.",
                    "Late analyses: no changes selected.",
                )
            )
            return

        applied_count = len(well.analysis_update_history[-1].changes)
        self._acknowledge_background_project_save()
        self._refresh_cuttings_after_edit()
        self.statusBar().showMessage(
            self._late_analysis_text(
                f"Поздние анализы сохранены: применено изменений — {applied_count}.",
                f"Кейінгі талдаулар сақталды: қолданылған өзгерістер — {applied_count}.",
                f"Late analyses saved: {applied_count} change(s) applied.",
            )
        )

    def show_canvas_object_transfer(self) -> None:
        well = self.session.current_well
        title = self._canvas_object_transfer_text(
            "Перенос пользовательских рисунков",
            "Пайдаланушы суреттерін көшіру",
            "Transfer authored drawings",
        )
        if well is None:
            QMessageBox.information(
                self,
                title,
                self._canvas_object_transfer_text(
                    "Сначала выберите скважину.",
                    "Алдымен ұңғыманы таңдаңыз.",
                    "Select a well first.",
                ),
            )
            return
        if self.project_path is None:
            QMessageBox.information(
                self,
                title,
                self._canvas_object_transfer_text(
                    "Сначала сохраните проект: подтверждённый перенос должен быть "
                    "сразу записан в файл проекта.",
                    "Алдымен жобаны сақтаңыз: расталған көшіру жоба файлына бірден "
                    "жазылуы тиіс.",
                    "Save the project first: a confirmed transfer must be persisted "
                    "to the project file immediately.",
                ),
            )
            return

        controller = CanvasObjectTransferController(self.session)
        workflow = CanvasObjectTransferWorkflow(
            self.session,
            controller,
            self.project_controller,
        )
        dialog = CanvasObjectTransferDialog(
            workflow,
            well.well_id,
            language=self.language,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        outcome = dialog.outcome
        if outcome is None or not outcome.copied_object_ids:
            self.statusBar().showMessage(
                self._canvas_object_transfer_text(
                    "Перенос рисунков: изменений нет.",
                    "Суреттерді көшіру: өзгерістер жоқ.",
                    "Drawing transfer: no changes.",
                )
            )
            return

        copied_count = len(outcome.copied_object_ids)
        self._acknowledge_background_project_save()
        self._refresh_transferred_canvas_layer(well.well_id)
        self.statusBar().showMessage(
            self._canvas_object_transfer_text(
                f"Рисунки перенесены и сохранены: {copied_count}.",
                f"Суреттер көшіріліп, сақталды: {copied_count}.",
                f"Drawings transferred and saved: {copied_count}.",
            )
        )

    def _refresh_transferred_canvas_layer(self, target_well_id: str) -> None:
        """Render transferred objects without mutating the just-saved project."""

        well = self.session.current_well
        if well is None or well.well_id != target_well_id:
            return
        scope_id = annotation_scope_id_for_session(self.session)
        visible_objects = [
            item
            for item in well.canvas_objects
            if is_annotation_object(item)
            and annotation_matches_scope(annotation_from_canvas(item), scope_id)
        ]
        self.tablet_view.set_image_assets(self.session.image_assets)
        self.tablet_view.set_canvas_objects(visible_objects)

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

    def _clear_interpretation_interval_selection(self) -> None:
        coordinator = self.interpretation_feature_coordinator
        if coordinator is None:
            super()._clear_interpretation_interval_selection()
            return
        coordinator.clear_interval_selection()
        self.tablet_view.clear_interval_selection()
        self.interpretation_properties.clear()
        self.interpretation_properties_dock.hide()

    def _after_interpretation_change(self) -> None:
        coordinator = self.interpretation_feature_coordinator
        if coordinator is None:
            super()._after_interpretation_change()
            return
        state = coordinator.sync_after_change()
        self.tablet_view.set_interpretations(
            list(state.interpretations),
            state.selected_interpretation_id,
        )
        if state.selected_interpretation_id and state.selected_interval_id:
            self._select_interpretation_interval(
                state.selected_interpretation_id,
                state.selected_interval_id,
            )
        else:
            self._clear_interpretation_interval_selection()
        self._refresh_tree()
        self._update_title()
        self._update_interpretation_history_actions()

    def change_language(self, language: AppLanguage) -> None:
        super().change_language(language)
        if hasattr(self, "drilling_calculation_action"):
            self._retranslate_drilling_calculation_action()
        if hasattr(self, "late_analysis_import_action"):
            self._retranslate_late_analysis_action()
        if hasattr(self, "canvas_object_transfer_action"):
            self._retranslate_canvas_object_transfer_action()

    def _retranslate_late_analysis_action(self) -> None:
        text = self._late_analysis_text(
            "Импорт поздних анализов…",
            "Кейінгі талдауларды импорттау…",
            "Import late analyses…",
        )
        tooltip = self._late_analysis_text(
            "Сопоставить поздние лабораторные анализы с существующими интервалами "
            "шлама без перезаписи заполненных значений.",
            "Кейінгі зертханалық талдауларды бар шлам аралықтарымен сәйкестендіріп, "
            "толтырылған мәндерді қайта жазбау.",
            "Match late laboratory analyses to existing cuttings intervals without "
            "overwriting populated values.",
        )
        self.late_analysis_import_action.setText(text)
        self.late_analysis_import_action.setToolTip(tooltip)
        self.late_analysis_import_action.setStatusTip(tooltip)

    def _retranslate_canvas_object_transfer_action(self) -> None:
        text = self._canvas_object_transfer_text(
            "Перенести пользовательские рисунки из другой скважины…",
            "Басқа ұңғымадан пайдаланушы суреттерін көшіру…",
            "Transfer authored drawings from another well…",
        )
        tooltip = self._canvas_object_transfer_text(
            "Просмотреть и явно перенести выбранные пользовательские рисунки из другой "
            "скважины без перезаписи существующих объектов.",
            "Басқа ұңғымадан таңдалған пайдаланушы суреттерін қарап, бар объектілерді "
            "қайта жазбай нақты көшіру.",
            "Review and explicitly transfer selected authored drawings from another well "
            "without overwriting existing objects.",
        )
        self.canvas_object_transfer_action.setText(text)
        self.canvas_object_transfer_action.setToolTip(tooltip)
        self.canvas_object_transfer_action.setStatusTip(tooltip)

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

    def _late_analysis_text(self, ru: str, kk: str, en: str) -> str:
        return {AppLanguage.RU: ru, AppLanguage.KK: kk, AppLanguage.EN: en}[
            self.language
        ]

    def _canvas_object_transfer_text(self, ru: str, kk: str, en: str) -> str:
        return {AppLanguage.RU: ru, AppLanguage.KK: kk, AppLanguage.EN: en}[
            self.language
        ]

    def _drilling_text(self, ru: str, kk: str, en: str) -> str:
        return {AppLanguage.RU: ru, AppLanguage.KK: kk, AppLanguage.EN: en}[
            self.language
        ]


__all__ = ["MainWindow"]
