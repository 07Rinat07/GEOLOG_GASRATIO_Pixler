from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import tempfile
from typing import TYPE_CHECKING

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter

from geoworkbench.domain.depth_interval import scope_dataset
from geoworkbench.domain.models import Dataset
from geoworkbench.printing.hydrocarbon_interpretation_pdf_renderer import (
    render_hydrocarbon_interpretation_report,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology import (
    InterpretationGeologySnapshot,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS,
    InterpretationGeologyTrackSettings,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    InterpretationReportIdentity,
    default_interpretation_report_identity,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_range import (
    ReportDepthRangeError,
    resolve_report_depth_range,
    scope_report_to_depth_range,
)
from geoworkbench.printing.report_visual_system import REPORT_BRAND_WORDMARK
from geoworkbench.printing.unicode_support import preflight_texts
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
    hydrocarbon_interpretation_html,
)
from geoworkbench.services.report_output_transaction import (
    ReportOutputTransactionResult,
    execute_report_output_transaction,
)
from geoworkbench.services.report_passport import (
    ReportKind,
    ReportPassportBuilder,
    ReportPassportRequest,
    ReportRenderSettings,
)
from geoworkbench.services.localization import AppLanguage

if TYPE_CHECKING:
    from geoworkbench.project.session import ProjectSession


class HydrocarbonInterpretationPdfError(RuntimeError):
    pass


def export_hydrocarbon_interpretation_pdf_with_passport(
    session: "ProjectSession",
    report: HydrocarbonInterpretationReport,
    target: str | Path,
    *,
    language: AppLanguage = AppLanguage.RU,
    include_chart: bool = False,
    orientation: QPageLayout.Orientation = QPageLayout.Orientation.Landscape,
    identity: InterpretationReportIdentity | None = None,
    geology: InterpretationGeologySnapshot | None = None,
    geology_track_settings: InterpretationGeologyTrackSettings = (
        DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS
    ),
    overwrite: bool = False,
) -> ReportOutputTransactionResult:
    dataset = session.current_dataset
    if dataset is None:
        raise HydrocarbonInterpretationPdfError(
            "Для interpretation Report Passport требуется выбранный dataset"
        )
    destination = Path(target)
    if destination.suffix.casefold() != ".pdf":
        destination = destination.with_suffix(".pdf")
    details = (
        identity
        or default_interpretation_report_identity(report, language)
    ).cleaned()
    if report.analysis_depth_interval is not None:
        details = replace(details, interval=report.analysis_depth_interval.formatted(report.depth_unit))
    try:
        depth_range = report.analysis_depth_interval or resolve_report_depth_range(details.interval, dataset)
    except ReportDepthRangeError as exc:
        raise HydrocarbonInterpretationPdfError(
            f"Некорректный интервал отчёта: {exc}"
        ) from exc

    passport = ReportPassportBuilder().build(
        session,
        ReportPassportRequest(
            report_kind=ReportKind.INTERPRETATION,
            report_name=details.report_title,
            language=language.value,
            render=ReportRenderSettings(
                renderer="interpretation-report:1",
                output_format="pdf",
                page_format="a4",
                orientation=orientation.name.casefold(),
                dpi=72,
                margins_mm=(14.0, 14.0, 14.0, 14.0),
                options=(
                    ("geology_cuttings", geology_track_settings.cuttings.value),
                    ("geology_lba", geology_track_settings.lba.value),
                ),
            ),
            interval=(depth_range.top_depth, depth_range.bottom_depth),
            curve_mnemonics=_interpretation_passport_curve_mnemonics(report),
        ),
    )

    return execute_report_output_transaction(
        destination,
        lambda staged: export_hydrocarbon_interpretation_pdf(
            report,
            staged,
            language=language,
            dataset=dataset,
            include_chart=include_chart,
            orientation=orientation,
            identity=details,
            geology=geology,
            geology_track_settings=geology_track_settings,
            overwrite=True,
        ),
        passport,
        overwrite=overwrite,
    )


def _interpretation_passport_curve_mnemonics(
    report: HydrocarbonInterpretationReport,
) -> tuple[str, ...] | None:
    values = tuple(
        dict.fromkeys(
            mnemonic
            for method in report.methods
            for mnemonic in method.available_mnemonics
            if mnemonic.strip()
        )
    )
    return values or None


def export_hydrocarbon_interpretation_pdf(
    report: HydrocarbonInterpretationReport,
    target: str | Path,
    *,
    language: AppLanguage = AppLanguage.RU,
    dataset: Dataset | None = None,
    include_chart: bool = False,
    orientation: QPageLayout.Orientation = QPageLayout.Orientation.Landscape,
    identity: InterpretationReportIdentity | None = None,
    geology: InterpretationGeologySnapshot | None = None,
    geology_track_settings: InterpretationGeologyTrackSettings = (
        DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS
    ),
    overwrite: bool = False,
) -> Path:
    destination = Path(target)
    if destination.suffix.casefold() != ".pdf":
        destination = destination.with_suffix(".pdf")
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}-",
        suffix=".pdf",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    details = (
        identity
        or default_interpretation_report_identity(report, language)
    ).cleaned()
    if report.analysis_depth_interval is not None:
        details = replace(details, interval=report.analysis_depth_interval.formatted(report.depth_unit))
    effective_report = report
    depth_range = None
    if dataset is not None:
        try:
            depth_range = report.analysis_depth_interval or resolve_report_depth_range(details.interval, dataset)
        except ReportDepthRangeError as exc:
            temporary.unlink(missing_ok=True)
            raise HydrocarbonInterpretationPdfError(
                f"Некорректный интервал отчёта: {exc}"
            ) from exc
        effective_report = scope_report_to_depth_range(report, depth_range)
        if details.interval:
            details = replace(
                details,
                interval=depth_range.formatted(report.depth_unit),
            )
    try:
        writer = QPdfWriter(str(temporary))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(orientation)
        writer.setPageMargins(
            QMarginsF(14.0, 14.0, 14.0, 14.0),
            QPageLayout.Unit.Millimeter,
        )
        # The renderer works in PostScript points. At 72 DPI one logical
        # painter unit is exactly one point, so fonts and chart geometry share
        # the same physical scale without an additional DPI transform.
        writer.setResolution(72)
        writer.setTitle(details.report_title)
        writer.setCreator(REPORT_BRAND_WORDMARK)

        html = hydrocarbon_interpretation_html(effective_report, language)
        if dataset is not None:
            from geoworkbench.services.hydrocarbon_interpretation_gas_html import (
                inject_interval_gas_statistics_html,
            )

            html = inject_interval_gas_statistics_html(
                html,
                effective_report,
                scope_dataset(dataset, report.analysis_depth_interval),
                language,
            )
        identity_texts = (
            details.report_title,
            details.report_subtitle,
            details.project_name,
            details.well_name,
            details.field_name,
            details.location,
            details.operator_name,
            details.contractor_name,
            details.rig_name,
            details.dataset_name,
            details.interval,
            details.document_number,
            details.revision,
            details.document_status,
            details.report_date,
            details.prepared_by,
            details.checked_by,
            details.approved_by,
            details.confidentiality,
            details.remarks,
        )
        unicode_report = preflight_texts([html, *identity_texts])
        if not unicode_report.ok:
            raise HydrocarbonInterpretationPdfError(unicode_report.error_message())

        render_hydrocarbon_interpretation_report(
            writer,
            effective_report,
            language=language,
            dataset=dataset,
            include_chart=include_chart,
            identity=details,
            depth_range=depth_range,
            geology=geology,
            geology_track_settings=geology_track_settings,
        )
        del writer
        if temporary.stat().st_size <= 0:
            raise HydrocarbonInterpretationPdfError("Не удалось сформировать PDF-отчёт")
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, (FileExistsError, HydrocarbonInterpretationPdfError)):
            raise
        raise HydrocarbonInterpretationPdfError(
            f"Не удалось экспортировать PDF: {destination}"
        ) from exc
    return destination
