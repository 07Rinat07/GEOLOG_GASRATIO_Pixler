from __future__ import annotations

from dataclasses import replace

from geoworkbench.catalogs.sensors import normalize_unit
from geoworkbench.domain.models import Dataset
from geoworkbench.services.hydrocarbon_interpretation_legacy import (
    GasContextIntervalAudit,
    GasContextMeasuredCurveStats,
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.interval_gas_statistics import (
    IntervalCurveStatistics,
    build_interval_statistics,
)
from geoworkbench.services.las_parameter_resolver import concentration_scale_to_percent


def attach_gas_context_measurement_audit(
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
) -> HydrocarbonInterpretationReport:
    """Attach measured interval gas statistics without mutating source curves.

    Manual TG/QC is retained as an operator reference. A QC delta is produced only
    when the manual unit and the measured total-gas unit are safely comparable as
    concentration units; it is defined as manual reference minus measured interval mean.
    """

    rows: list[GasContextIntervalAudit] = []
    for event in report.gas_context_events:
        statistics = build_interval_statistics(
            dataset,
            event.top_depth,
            event.bottom_depth,
        )
        measured_total = _copy_stats(statistics.raw_total)
        components = tuple(_copy_stats(item) for item in statistics.components)
        rows.append(
            GasContextIntervalAudit(
                event_id=event.event_id,
                measured_total_gas=measured_total,
                measured_components=tuple(item for item in components if item is not None),
                manual_total_gas=event.reported_total_gas,
                manual_unit=event.reported_unit or "",
                qc_delta_vs_measured_mean=_qc_delta(
                    event.reported_total_gas,
                    event.reported_unit or "",
                    measured_total,
                ),
                qc_delta_unit=_qc_delta_unit(
                    event.reported_total_gas,
                    event.reported_unit or "",
                    measured_total,
                ),
            )
        )
    return replace(report, gas_context_audit=tuple(rows))


def _copy_stats(
    item: IntervalCurveStatistics | None,
) -> GasContextMeasuredCurveStats | None:
    if item is None:
        return None
    return GasContextMeasuredCurveStats(
        mnemonic=item.mnemonic,
        unit=item.unit,
        minimum=item.minimum,
        mean=item.mean,
        maximum=item.maximum,
    )


def _qc_delta(
    manual_value: float | None,
    manual_unit: str,
    measured: GasContextMeasuredCurveStats | None,
) -> float | None:
    if manual_value is None or measured is None or measured.mean is None:
        return None
    manual_scale = concentration_scale_to_percent(manual_unit)
    measured_scale = concentration_scale_to_percent(measured.unit)
    if manual_scale is None or measured_scale is None:
        if normalize_unit(manual_unit).casefold() != normalize_unit(measured.unit).casefold():
            return None
        return float(manual_value - measured.mean)
    return float(manual_value * manual_scale - measured.mean * measured_scale)


def _qc_delta_unit(
    manual_value: float | None,
    manual_unit: str,
    measured: GasContextMeasuredCurveStats | None,
) -> str:
    if _qc_delta(manual_value, manual_unit, measured) is None:
        return ""
    manual_scale = concentration_scale_to_percent(manual_unit)
    measured_scale = concentration_scale_to_percent(measured.unit if measured is not None else "")
    if manual_scale is not None and measured_scale is not None:
        return "%vol"
    return measured.unit if measured is not None else manual_unit


__all__ = ["attach_gas_context_measurement_audit"]
