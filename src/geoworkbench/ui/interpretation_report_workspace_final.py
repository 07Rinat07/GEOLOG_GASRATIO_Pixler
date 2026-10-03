from __future__ import annotations

from dataclasses import replace
import logging
from pathlib import Path
import tempfile

import fitz
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import QAbstractPrintDialog, QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QProgressDialog,
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QDoubleSpinBox,
    QPushButton,
    QLabel,
)

from geoworkbench.domain.depth_interval import DepthInterval, DepthIntervalError
from geoworkbench.domain.models import IndexRole
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.edit_history import CommandHistory
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)

from geoworkbench.data.hydrocarbon_interpretation_export import (
    HydrocarbonInterpretationExportError,
)
from geoworkbench.printing.gas_mixture_ramp_report import GasMixtureRampReport
from geoworkbench.printing.hydrocarbon_interpretation_chart_front import (
    hydrocarbon_interpretation_html_with_front_chart,
)
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    HydrocarbonInterpretationPdfError,
    export_hydrocarbon_interpretation_pdf,
    export_hydrocarbon_interpretation_pdf_with_passport,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology import (
    interpretation_geology_snapshot,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS,
    InterpretationGeologyTrackSettings,
    geology_track_settings_from_composition,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    InterpretationReportIdentity,
    default_interpretation_report_identity,
    identity_with_report_header_fields,
    report_header_fields_from_identity,
)
from geoworkbench.domain.report_composition import (
    DEFAULT_INTERPRETATION_REPORT_COMPOSITION,
    InterpretationReportComposition,
    ensure_report_composition_id,
    report_header_fields,
    with_report_header_fields,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_range import (
    ReportDepthRangeError,
    resolve_report_depth_range,
)
from geoworkbench.printing.hydrocarbon_interpretation_system_print import (
    configure_interpretation_printer,
    print_pdf_page_selection,
    selected_report_pages,
)
from geoworkbench.printing.hydrocarbon_report_print_i18n import (
    hydrocarbon_report_print_labels,
)
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
)
from geoworkbench.ui.interpretation_print_layout_dialog import (
    InterpretationPrintLayoutDialog,
    InterpretationPrintOrder,
)
from geoworkbench.ui.interpretation_report_details_dialog import (
    InterpretationReportDetailsDialog,
)
from geoworkbench.ui.interpretation_report_annotation_dialog import (
    InterpretationReportAnnotationDialog,
)
from geoworkbench.ui.interpretation_report_workspace_expert import (
    InterpretationReportWorkspace as _ExpertInterpretationReportWorkspace,
)


LOGGER = logging.getLogger(__name__)


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
                "Создаёт один основной лист с УВ-интервалами и абсолютными компонентами "
                "газа C1, C2, C3, iC4, nC4, iC5, nC5. Для каждой кривой приводятся "
                "минимум, среднее и максимум. Исходные данные сохраняются на скрытом листе.",
                "Көмірсутек аралықтары және C1, C2, C3, iC4, nC4, iC5, nC5 абсолюттік газ "
                "компоненттері бар негізгі парақ жасайды. Әр қисық үшін ең аз, орташа және "
                "ең көп мән беріледі. Бастапқы деректер жасырын парақта сақталады.",
                "Creates one main sheet with hydrocarbon intervals and absolute C1, C2, C3, "
                "iC4, nC4, iC5, and nC5 gas components. Each curve includes minimum, mean, "
                "and maximum values. Source data remain on a hidden audit sheet.",
            )
        )

    def __init__(
        self,
        controller: InterpretationCalculationController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(controller, parent, language=language)
        self.depth_interval_panel = QWidget(self)
        self.depth_interval_panel.setObjectName("interpretation-depth-interval")
        form = QFormLayout(self.depth_interval_panel)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.depth_interval_mode = QComboBox()
        self.depth_interval_mode.addItems(["", ""])
        self.depth_interval_top = QDoubleSpinBox()
        self.depth_interval_bottom = QDoubleSpinBox()
        self.depth_interval_mode.setObjectName("analysis-depth-mode")
        self.depth_interval_top.setObjectName("analysis-depth-top")
        self.depth_interval_bottom.setObjectName("analysis-depth-bottom")
        for spin in (self.depth_interval_top, self.depth_interval_bottom):
            spin.setDecimals(6)
            spin.setRange(-1.0e12, 1.0e12)
        self.depth_interval_apply = QPushButton()
        self.depth_interval_apply.setObjectName("apply-analysis-depth-interval")
        self.depth_interval_note = QLabel()
        self.depth_interval_note.setWordWrap(True)
        self.depth_interval_mode_label = QLabel()
        self.depth_interval_top_label = QLabel()
        self.depth_interval_bottom_label = QLabel()
        form.addRow(self.depth_interval_mode_label, self.depth_interval_mode)
        form.addRow(self.depth_interval_top_label, self.depth_interval_top)
        form.addRow(self.depth_interval_bottom_label, self.depth_interval_bottom)
        form.addRow(self.depth_interval_apply)
        form.addRow(self.depth_interval_note)
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            raise RuntimeError("Не найден layout отчёта интерпретации")
        root.addWidget(self.depth_interval_panel)
        self.report_annotations_button = QPushButton(self)
        self.report_annotations_button.setObjectName("edit-report-annotations")
        root.addWidget(self.report_annotations_button)
        self._report_annotation_history = CommandHistory(max_commands=100)
        self._depth_interval_dataset_key: tuple[object, ...] | None = None
        self._depth_interval_endpoints: tuple[tuple[float, float], tuple[float, float]] | None = None
        self._preview_geology_report_key: tuple[object, ...] | None = None
        self._preview_depth_range: DepthInterval | None = None
        self.depth_interval_apply.clicked.connect(self._apply_depth_interval)
        self.depth_interval_mode.currentIndexChanged.connect(self._update_depth_interval_controls)
        self.report_annotations_button.clicked.connect(self._edit_report_annotations)
        self.refresh()

    def refresh(self) -> None:
        if hasattr(self, "depth_interval_panel"):
            self._sync_depth_interval_dataset()
            self._retranslate_depth_interval()
            self._update_depth_interval_controls()
        super().refresh()

    def set_language(self, language: AppLanguage) -> None:
        super().set_language(language)
        if hasattr(self, "depth_interval_panel"):
            self._retranslate_depth_interval()
        if hasattr(self, "report_annotations_button"):
            self._retranslate_report_annotations()

    def _sync_depth_interval_dataset(self) -> None:
        session = self.controller.session
        dataset = session.current_dataset
        key = (
            None
            if dataset is None
            else (session.current_well_id, dataset.dataset_id, dataset.active_index_id, id(dataset))
        )
        if key == self._depth_interval_dataset_key:
            return
        self._depth_interval_dataset_key = key
        self._preview_geology_report_key = None
        self.controller.depth_interval = None
        self.depth_interval_mode.setCurrentIndex(0)
        self._preview_depth_range = None
        self._depth_interval_endpoints = None
        if dataset is not None and dataset.active_index.role is IndexRole.DEPTH:
            finite = dataset.depth[np.isfinite(dataset.depth)]
            if finite.size:
                top, bottom = float(finite.min()), float(finite.max())
                self.depth_interval_top.setValue(top)
                self.depth_interval_bottom.setValue(bottom)
                # Keep exact LAS endpoints behind their rounded control values.
                # Both outward rounding and inward rounding must retain the
                # first and last measurements of an unchanged full interval.
                self._depth_interval_endpoints = (
                    (self.depth_interval_top.value(), top),
                    (self.depth_interval_bottom.value(), bottom),
                )
                for spin in (self.depth_interval_top, self.depth_interval_bottom):
                    spin.setSuffix(f" {dataset.active_index.unit or ''}")

    def _retranslate_depth_interval(self) -> None:
        self.depth_interval_mode_label.setText(
            self._text("Область расчёта", "Есептеу аумағы", "Analysis scope")
        )
        self.depth_interval_mode.setItemText(
            0, self._text("Вся скважина", "Бүкіл ұңғыма", "Whole well")
        )
        self.depth_interval_mode.setItemText(
            1, self._text("Интервал глубин", "Тереңдік аралығы", "Depth interval")
        )
        self.depth_interval_top_label.setText(self._text("Кровля", "Жоғарғы шекара", "Top depth"))
        self.depth_interval_bottom_label.setText(
            self._text("Подошва", "Төменгі шекара", "Bottom depth")
        )
        self.depth_interval_apply.setText(
            self._text("Применить интервал", "Аралықты қолдану", "Apply interval")
        )
        interval = self.controller.depth_interval
        value = (
            interval.formatted() if interval is not None else self.depth_interval_mode.itemText(0)
        )
        self.depth_interval_note.setText(
            self._text(
                f"Применено: {value}. Расчёты, фон, интерпретация, графики, литология и ЛБА используют эту область.",
                f"Қолданылды: {value}. Есептеу, фон, интерпретация, графиктер, литология және ЛБА осы аумақты қолданады.",
                f"Applied: {value}. Calculations, background, interpretation, charts, lithology and LBA use this scope.",
            )
        )

    def _retranslate_report_annotations(self) -> None:
        count = len(self._report_composition().annotations)
        self.report_annotations_button.setText(
            self._text(
                f"Аннотации итогового отчёта… ({count})",
                f"Қорытынды есеп аннотациялары… ({count})",
                f"Final report annotations… ({count})",
            )
        )

    def _update_depth_interval_controls(self) -> None:
        dataset = self.controller.session.current_dataset
        enabled = (
            dataset is not None
            and dataset.active_index.role is IndexRole.DEPTH
            and not self._is_mixture_mode()
        )
        self.depth_interval_panel.setEnabled(enabled)
        selected = self.depth_interval_mode.currentIndex() == 1
        self.depth_interval_top.setEnabled(selected)
        self.depth_interval_bottom.setEnabled(selected)

    def _apply_depth_interval(self) -> None:
        dataset = self.controller.session.current_dataset
        if dataset is None:
            return
        try:
            interval = None
            if self.depth_interval_mode.currentIndex() == 1:
                top, bottom = self.depth_interval_top.value(), self.depth_interval_bottom.value()
                endpoints = self._depth_interval_endpoints
                if endpoints is not None:
                    if top == endpoints[0][0]:
                        top = endpoints[0][1]
                    if bottom == endpoints[1][0]:
                        bottom = endpoints[1][1]
                interval = DepthInterval(top, bottom)
                interval.row_mask(dataset)
        except DepthIntervalError as exc:
            self.depth_interval_note.setText(str(exc))
            return
        self.controller.depth_interval = interval
        self._preview_geology_report_key = None
        self.refresh()

    def _edit_report_annotations(self) -> None:
        if self.controller.session.current_dataset is None or self._is_mixture_mode():
            return
        dialog = InterpretationReportAnnotationDialog(
            self.controller.session,
            self,
            language=self.language,
            shared_history=self._report_annotation_history,
            on_changed=self._report_annotations_changed,
        )
        dialog.exec()
        self._report_annotations_changed()

    def _report_annotations_changed(self) -> None:
        self._preview_geology_report_key = None
        self._retranslate_report_annotations()
        self._apply_chart_preview()

    def _open_tablet(self) -> None:
        super()._open_tablet()
        interval = self.controller.depth_interval
        tablet = getattr(self.window(), "tablet_view", None)
        set_depth = getattr(tablet, "set_visible_depth", None)
        if interval is not None and callable(set_depth):
            set_depth(interval.top_depth, interval.bottom_depth)

    def _apply_chart_preview(self) -> None:
        dataset = self.controller.session.current_dataset
        report = self.report
        if report is None or dataset is None or self._is_mixture_mode():
            return
        geology = interpretation_geology_snapshot(self.controller.session)
        composition = self._report_composition()
        key = self._preview_report_key(report)
        if getattr(self, "_preview_geology_report_key", None) == key:
            geology_track_settings = getattr(
                self,
                "_preview_geology_track_settings",
                DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS,
            )
            depth_range = getattr(self, "_preview_depth_range", None)
        else:
            geology_track_settings = geology_track_settings_from_composition(composition)
            depth_range = None
        depth_range = getattr(report, "analysis_depth_interval", None) or depth_range
        persisted_header = report_header_fields(
            composition,
            self.language.value,
            report.report_profile,
        )
        preview_identity = (
            identity_with_report_header_fields(
                default_interpretation_report_identity(
                    report,
                    self.language,
                    interval=self._report_interval(report),
                ),
                persisted_header,
            )
            if persisted_header is not None
            else None
        )
        self.preview.setHtml(
            hydrocarbon_interpretation_html_with_front_chart(
                report,
                dataset,
                self.language,
                geology=geology,
                geology_track_settings=geology_track_settings,
                depth_range=depth_range,
                legend_mode=composition.legend_mode,
                layout_profile=composition.layout_profile,
                identity=preview_identity,
                annotations=composition.annotations,
            )
        )

    def _report_composition(self) -> InterpretationReportComposition:
        dataset = self.controller.session.current_dataset
        if dataset is None:
            return DEFAULT_INTERPRETATION_REPORT_COMPOSITION
        return self.controller.session.report_compositions.get(
            dataset.dataset_id,
            DEFAULT_INTERPRETATION_REPORT_COMPOSITION,
        )

    def _store_report_composition(
        self,
        composition: InterpretationReportComposition,
    ) -> None:
        dataset = self.controller.session.current_dataset
        if dataset is None:
            return
        composition = ensure_report_composition_id(composition, dataset.dataset_id)
        current = self.controller.session.report_compositions.get(dataset.dataset_id)
        if current == composition:
            return
        self.controller.session.report_compositions[dataset.dataset_id] = composition
        self.controller.session.dirty = True
        self._preview_geology_report_key = None

    @staticmethod
    def _preview_report_key(
        report: HydrocarbonInterpretationReport,
    ) -> tuple[object, ...]:
        return (
            report.project_name,
            report.well_name,
            report.dataset_id,
            report.report_profile,
            getattr(report, "analysis_depth_interval", None),
        )

    def _sync_preview_geology_composition(
        self,
        report: HydrocarbonInterpretationReport,
        identity: InterpretationReportIdentity,
        settings: InterpretationGeologyTrackSettings,
    ) -> bool:
        dataset = self.controller.session.current_dataset
        if dataset is None:
            return False
        try:
            depth_range = report.analysis_depth_interval or resolve_report_depth_range(
                identity.interval,
                dataset,
                language=self.language,
            )
        except ReportDepthRangeError as exc:
            self._show_export_error(exc)
            return False
        self._preview_geology_report_key = self._preview_report_key(report)
        self._preview_geology_track_settings = settings
        self._preview_depth_range = depth_range
        self._apply_chart_preview()
        return True

    def _export_pdf(self) -> None:
        report = self._require_any_report()
        if report is None:
            return
        if isinstance(report, GasMixtureRampReport):
            super()._export_pdf()
            return
        dataset = self.controller.session.current_dataset
        if dataset is None:
            return
        geology = interpretation_geology_snapshot(self.controller.session)

        identity = self._select_report_identity(report)
        if identity is None:
            return
        layout_dialog = InterpretationPrintLayoutDialog(
            self,
            language=self.language,
            include_order=False,
            initial=self._report_composition(),
        )
        if layout_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        layout = layout_dialog.selected_layout()
        composition = with_report_header_fields(
            layout_dialog.selected_composition(),
            self.language.value,
            report_header_fields_from_identity(identity, report.report_profile),
        )
        self._store_report_composition(composition)
        if not self._sync_preview_geology_composition(
            report,
            identity,
            layout.geology_tracks,
        ):
            return
        target = self._choose_target(".pdf", "PDF (*.pdf)")
        if target is None:
            return
        try:
            with self._report_export_progress(
                self._text(
                    "Формируется PDF-отчёт с графиками…",
                    "Графиктері бар PDF есебі құрылуда…",
                    "Building PDF report with charts…",
                )
            ):
                export_result = export_hydrocarbon_interpretation_pdf_with_passport(
                    self.controller.session,
                    report,
                    target,
                    language=self.language,
                    include_chart=True,
                    orientation=layout.orientation,
                    identity=identity,
                    geology=geology,
                    geology_track_settings=layout.geology_tracks,
                    legend_mode=layout.legend_mode,
                    layout_profile=layout.layout_profile,
                    annotations=composition.annotations,
                    overwrite=target.exists(),
                )
                exported = export_result.primary_path
        except (OSError, FileExistsError, HydrocarbonInterpretationPdfError) as exc:
            self._show_export_error(exc)
            return
        self._show_export_success(exported)

    def _print_report(self) -> None:
        report = self._require_any_report()
        if report is None:
            return
        if isinstance(report, GasMixtureRampReport):
            super()._print_report()
            return
        dataset = self.controller.session.current_dataset
        if dataset is None:
            return
        geology = interpretation_geology_snapshot(self.controller.session)

        identity = self._select_report_identity(report)
        if identity is None:
            return
        layout_dialog = InterpretationPrintLayoutDialog(
            self,
            language=self.language,
            initial=self._report_composition(),
        )
        if layout_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        layout = layout_dialog.selected_layout()
        composition = with_report_header_fields(
            layout_dialog.selected_composition(),
            self.language.value,
            report_header_fields_from_identity(identity, report.report_profile),
        )
        self._store_report_composition(composition)
        if not self._sync_preview_geology_composition(
            report,
            identity,
            layout.geology_tracks,
        ):
            return

        with tempfile.TemporaryDirectory(prefix="geolog-interpretation-print-") as folder:
            prepared_pdf = Path(folder) / "interpretation-report.pdf"
            try:
                export_hydrocarbon_interpretation_pdf(
                    report,
                    prepared_pdf,
                    language=self.language,
                    dataset=dataset,
                    include_chart=True,
                    orientation=layout.orientation,
                    identity=identity,
                    geology=geology,
                    geology_track_settings=layout.geology_tracks,
                    legend_mode=layout.legend_mode,
                    layout_profile=layout.layout_profile,
                    annotations=composition.annotations,
                    overwrite=True,
                )
                with fitz.open(prepared_pdf) as document:
                    total_pages = document.page_count
            except (OSError, HydrocarbonInterpretationPdfError, RuntimeError) as exc:
                self._show_export_error(exc)
                return
            if total_pages < 1:
                self._show_export_error(
                    RuntimeError(
                        hydrocarbon_report_print_labels(self.language).print_report_no_pages
                    )
                )
                return

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            configure_interpretation_printer(printer, layout.orientation)
            printer.setDocName(identity.report_title)
            dialog = QPrintDialog(printer, self)
            dialog.setWindowTitle(identity.report_title)
            dialog.setOption(
                QAbstractPrintDialog.PrintDialogOption.PrintPageRange,
                True,
            )
            dialog.setOption(
                QAbstractPrintDialog.PrintDialogOption.PrintSelection,
                False,
            )
            dialog.setOption(
                QAbstractPrintDialog.PrintDialogOption.PrintCurrentPage,
                False,
            )
            dialog.setMinMax(1, total_pages)
            dialog.setFromTo(1, total_pages)
            dialog.setPrintRange(QAbstractPrintDialog.PrintRange.AllPages)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            range_selected = (
                dialog.printRange() == QAbstractPrintDialog.PrintRange.PageRange
                or printer.printRange() == QPrinter.PrintRange.PageRange
            )
            print_range = (
                QAbstractPrintDialog.PrintRange.PageRange
                if range_selected
                else QAbstractPrintDialog.PrintRange.AllPages
            )
            from_page = dialog.fromPage() or printer.fromPage()
            to_page = dialog.toPage() or printer.toPage()
            reverse = layout.order == InterpretationPrintOrder.LAST_TO_FIRST
            page_numbers = selected_report_pages(
                total_pages,
                print_range,
                from_page,
                to_page,
                reverse=reverse,
            )
            if not page_numbers:
                self._show_export_error(
                    RuntimeError(
                        hydrocarbon_report_print_labels(self.language).print_page_range_missing
                    )
                )
                return

            # Driver dialogs may change these values. Reapply the selected report
            # layout after acceptance so the prepared PDF and physical paper match.
            configure_interpretation_printer(printer, layout.orientation)
            LOGGER.info(
                "interpretation print start printer=%r orientation=%s range=%s-%s "
                "pages=%s order=%s copies=%s document=%r revision=%r well=%r",
                printer.printerName(),
                layout.orientation.name,
                page_numbers[0],
                page_numbers[-1],
                len(page_numbers),
                layout.order.value,
                printer.copyCount(),
                identity.document_number,
                identity.revision,
                identity.well_name,
            )

            progress = QProgressDialog(
                self._text(
                    "Подготовка страниц для принтера…",
                    "Принтерге арналған беттер дайындалуда…",
                    "Preparing pages for the printer…",
                ),
                self._text("Остановить", "Тоқтату", "Stop"),
                0,
                len(page_numbers),
                self,
            )
            progress.setWindowTitle(identity.report_title)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)

            def cancel_requested() -> bool:
                QApplication.processEvents()
                return progress.wasCanceled()

            def update_progress(current: int, total: int, page_number: int) -> None:
                progress.setLabelText(
                    self._text(
                        f"Отправляется страница {page_number} ({current} из {total})…",
                        f"{page_number}-бет жіберілуде ({current}/{total})…",
                        f"Sending page {page_number} ({current} of {total})…",
                    )
                )
                progress.setValue(current)
                QApplication.processEvents()

            try:
                completed = print_pdf_page_selection(
                    prepared_pdf,
                    printer,
                    page_numbers,
                    language=self.language,
                    cancel_requested=cancel_requested,
                    progress=update_progress,
                )
            except (OSError, RuntimeError, ValueError) as exc:
                LOGGER.exception("interpretation print failed")
                self._show_export_error(exc)
                return
            finally:
                progress.close()

            if not completed:
                LOGGER.warning(
                    "interpretation print cancelled printer=%r state=%s",
                    printer.printerName(),
                    printer.printerState().name,
                )
                self.status.setText(
                    self._text(
                        "Печать остановлена. Уже переданные в Windows страницы "
                        "могут остаться в очереди принтера.",
                        "Басып шығару тоқтатылды. Windows жүйесіне жіберілген "
                        "беттер принтер кезегінде қалуы мүмкін.",
                        "Printing was stopped. Pages already sent to Windows may "
                        "remain in the printer queue.",
                    )
                )
                return

            LOGGER.info(
                "interpretation print completed printer=%r pages=%s state=%s",
                printer.printerName(),
                len(page_numbers),
                printer.printerState().name,
            )
            self.status.setText(
                self._text(
                    f"В очередь печати отправлено страниц: {len(page_numbers)}.",
                    f"Басып шығару кезегіне {len(page_numbers)} бет жіберілді.",
                    f"Pages sent to the print queue: {len(page_numbers)}.",
                )
            )

    def _select_report_identity(
        self,
        report: HydrocarbonInterpretationReport,
    ) -> InterpretationReportIdentity | None:
        dataset = self.controller.session.current_dataset
        if dataset is None:
            return None
        defaults = default_interpretation_report_identity(
            report,
            self.language,
            interval=self._report_interval(report),
        )
        initial = identity_with_report_header_fields(
            defaults,
            report_header_fields(
                self._report_composition(),
                self.language.value,
                report.report_profile,
            ),
        )

        dialog = InterpretationReportDetailsDialog(
            defaults,
            self,
            language=self.language,
            initial=initial,
        )
        if hasattr(dialog, "interval"):
            dialog.interval.setReadOnly(True)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        selected = replace(dialog.selected_identity(), interval=defaults.interval)
        if not selected.report_title:
            selected = replace(selected, report_title=defaults.report_title)
        return selected

    def _report_interval(self, report: HydrocarbonInterpretationReport) -> str:
        if report.analysis_depth_interval is not None:
            return report.analysis_depth_interval.formatted(report.depth_unit)
        dataset = self.controller.session.current_dataset
        if dataset is None:
            return ""
        depth = np.asarray(dataset.depth, dtype=np.float64)
        finite = depth[np.isfinite(depth)]
        if finite.size < 1:
            return ""
        low = float(np.nanmin(finite))
        high = float(np.nanmax(finite))
        unit = report.depth_unit.strip()
        suffix = f" {unit}" if unit else ""
        return f"{low:.2f}–{high:.2f}{suffix}"

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

            with self._report_export_progress(
                self._text(
                    "Формируется Excel-отчёт…",
                    "Excel есебі құрылуда…",
                    "Building Excel report…",
                )
            ):
                exported = export_readable_hydrocarbon_interpretation_xlsx(
                    report,
                    dataset,
                    target,
                    language=self.language,
                    overwrite=target.exists(),
                    progress=self._update_report_export_progress,
                )
        except (OSError, FileExistsError, HydrocarbonInterpretationExportError) as exc:
            self._show_export_error(exc)
            return
        self._show_export_success(exported)


__all__ = ["InterpretationReportWorkspace"]
