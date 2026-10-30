from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from geoworkbench.data.hydrocarbon_interpretation_export import (
    HydrocarbonInterpretationExportError,
)
from geoworkbench.data.hydrocarbon_interpretation_export_docx_polished import (
    export_polished_hydrocarbon_interpretation_docx,
)
from geoworkbench.domain.report_composition import with_report_header_fields
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    report_header_fields_from_identity,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.services.drilling_input_plan import InputSourceMode
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.interpretation_geology_interval_evidence import GasGeologyIntervalEvidence
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

    def _export_docx(self) -> None:
        report = self._require_report()
        if report is None:
            return
        dataset = self.controller.session.current_dataset
        if dataset is None:
            return
        original_well_id = self.controller.session.current_well_id
        confirmed_geology = self._geology_word_evidence
        confirmed_field_selection = self._geology_word_field_selection
        identity = self._select_report_identity(report)
        if identity is None:
            return
        self._store_report_composition(
            with_report_header_fields(
                self._report_composition(),
                self._report_output_language().value,
                report_header_fields_from_identity(identity, report.report_profile),
            )
        )
        target = self._choose_target(".docx", "Word (*.docx)")
        if target is None:
            return
        try:
            with self._report_export_progress(
                self._text(
                    "Формируется Word-отчёт с отдельным титульным листом…",
                    "Жеке титулдық беті бар Word есебі құрылуда…",
                    "Building Word report with a separate cover page…",
                )
            ):
                if (
                    self.report is not report
                    or self.controller.session.current_dataset is not dataset
                    or self.controller.session.current_well_id != original_well_id
                ):
                    self._clear_geology_evidence()
                    self._clear_method_comparison()
                    raise HydrocarbonInterpretationExportError(
                        "Word report source changed during export preparation"
                    )
                comparisons = self._method_comparisons_for_export(report)
                selected_geology: tuple[GasGeologyIntervalEvidence, ...] = ()
                if confirmed_geology:
                    try:
                        selected_geology = self._geology_evidence_for_export(report, output="word")
                    except ValueError as exc:
                        raise HydrocarbonInterpretationExportError(
                            "Confirmed geology changed during Word preparation"
                        ) from exc
                    if selected_geology != confirmed_geology:
                        raise HydrocarbonInterpretationExportError(
                            "Confirmed geology was revoked during Word preparation"
                        )
                word_exporter: Callable[..., Path] = export_polished_hydrocarbon_interpretation_docx
                if comparisons:
                    word_exporter = partial(word_exporter, method_comparisons=comparisons)
                if selected_geology:
                    word_exporter = partial(word_exporter, geology_evidence=selected_geology)
                if confirmed_field_selection is not None:
                    if selected_geology:
                        raise HydrocarbonInterpretationExportError(
                            "Word measured-field and observation approvals must be separate"
                        )
                    try:
                        approved_fields, field_source_key = (
                            self._confirmed_geology_field_word_for_handoff(
                                report, confirmed_field_selection,
                            )
                        )
                    except ValueError as exc:
                        raise HydrocarbonInterpretationExportError(
                            "Operator-confirmed Word measured fields changed during preparation"
                        ) from exc
                    word_exporter = partial(
                        word_exporter,
                        session=self.controller.session,
                        geology_field_selection=approved_fields,
                        geology_source_key=field_source_key,
                    )
                exported = word_exporter(
                    report,
                    target,
                    dataset=dataset,
                    identity=identity,
                    language=self._report_output_language(),
                    overwrite=target.exists(),
                    orientation=self.word_orientation.currentData() or "portrait",
                )
        except (OSError, FileExistsError, ValueError, HydrocarbonInterpretationExportError) as exc:
            self._show_export_error(exc)
            return
        self._show_export_success(exported)

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
        self.docx_button.setToolTip(
            self._text(
                "Перед сохранением позволяет изменить реквизиты. Титульный лист Word "
                "и основные таблицы используют выбранную ориентацию A4.",
                "Сақтау алдында деректемелерді өзгертуге болады. Титулдық бет "
                "және кестелер таңдалған A4 бағытында болады.",
                "Lets you edit report details before saving. The cover and tables "
                "use the selected A4 page orientation.",
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
