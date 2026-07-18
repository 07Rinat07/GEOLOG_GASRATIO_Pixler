from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

import numpy as np

from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.masterlog_renderer import (
    MasterlogRenderError,
    masterlog_column_groups,
    masterlog_curve_bindings,
    masterlog_page_ranges,
    masterlog_page_size_mm,
)
from geoworkbench.services.time_depth_mapping import (
    TimeDepthMappingError,
    resolve_time_to_depth,
)


class PreflightSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class MasterlogPreflightIssue:
    code: str
    severity: PreflightSeverity
    values: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class MasterlogPreflightReport:
    issues: tuple[MasterlogPreflightIssue, ...]
    page_count: int

    @property
    def errors(self) -> tuple[MasterlogPreflightIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is PreflightSeverity.ERROR)

    @property
    def warnings(self) -> tuple[MasterlogPreflightIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is PreflightSeverity.WARNING)


def analyze_masterlog_output(
    template: MasterlogTemplate,
    session: ProjectSession,
    settings: MasterlogOutputSettings,
) -> MasterlogPreflightReport:
    issues: list[MasterlogPreflightIssue] = []
    dataset = session.current_dataset
    if dataset is None:
        issues.append(_issue("no_dataset", PreflightSeverity.ERROR))
    if not template.columns:
        issues.append(_issue("no_columns", PreflightSeverity.ERROR))
    page_size = masterlog_page_size_mm(template, session, settings)
    for element in template.header_elements:
        if (
            element.x_mm + element.width_mm > page_size.width()
            or element.y_mm + element.height_mm > template.header_height_mm
        ):
            issues.append(
                _issue(
                    "header_overflow",
                    PreflightSeverity.WARNING,
                    element=element.element_id,
                )
            )
        if element.element_type == "image":
            asset_ref = element.properties.get("asset_ref")
            if not isinstance(asset_ref, str) or asset_ref not in session.image_assets:
                issues.append(
                    _issue(
                        "missing_asset",
                        PreflightSeverity.WARNING,
                        element=element.element_id,
                    )
                )
    well = session.current_well
    if well is not None:
        columns_by_id = {column.column_id: column for column in template.columns}
        for item in well.canvas_objects:
            if (
                item.object_type != "masterlog_symbol"
                or item.properties.get("template_id") != template.template_id
            ):
                continue
            asset_ref = item.properties.get("asset_ref")
            if not isinstance(asset_ref, str) or asset_ref not in session.image_assets:
                issues.append(
                    _issue("missing_asset", PreflightSeverity.WARNING, element=item.object_id)
                )
            if item.track_id not in columns_by_id:
                issues.append(
                    _issue(
                        "missing_symbol_column",
                        PreflightSeverity.WARNING,
                        element=item.object_id,
                    )
                )
            symbol_top = item.top_depth if item.top_depth is not None else item.y
            symbol_bottom = item.bottom_depth
            invalid_anchor = item.anchor_type not in {"depth", "interval", "parameter", "time"}
            invalid_interval = item.anchor_type == "interval" and (
                not isinstance(symbol_top, (int, float))
                or isinstance(symbol_top, bool)
                or not isinstance(symbol_bottom, (int, float))
                or isinstance(symbol_bottom, bool)
                or not isfinite(float(symbol_top))
                or not isfinite(float(symbol_bottom))
                or float(symbol_bottom) <= float(symbol_top)
            )
            if invalid_anchor or invalid_interval:
                issues.append(
                    _issue(
                        "invalid_symbol_interval",
                        PreflightSeverity.WARNING,
                        element=item.object_id,
                    )
                )
            if item.anchor_type == "time":
                try:
                    if dataset is None or item.time_value is None:
                        raise TimeDepthMappingError("Нет TIME↔DEPTH mapping")
                    mapped = resolve_time_to_depth(dataset, item.time_value)
                    stored_depth = item.top_depth if item.top_depth is not None else item.y
                    if not isinstance(stored_depth, (int, float)) or not np.isclose(
                        float(stored_depth), mapped.depth
                    ):
                        raise TimeDepthMappingError("Сохранённая глубина устарела")
                except TimeDepthMappingError:
                    issues.append(
                        _issue(
                            "invalid_symbol_time",
                            PreflightSeverity.WARNING,
                            element=item.object_id,
                        )
                    )
            if item.anchor_type == "parameter":
                column = columns_by_id.get(str(item.track_id))
                mnemonic = item.parameter_mnemonic
                if (
                    column is None
                    or not isinstance(mnemonic, str)
                    or mnemonic not in column.curve_mnemonics
                    or dataset is None
                    or dataset.curve_by_mnemonic(mnemonic) is None
                ):
                    issues.append(
                        _issue(
                            "invalid_symbol_parameter",
                            PreflightSeverity.WARNING,
                            element=item.object_id,
                        )
                    )
    if dataset is not None:
        curve_bindings = masterlog_curve_bindings(template, dataset)
        for column in template.columns:
            if column.x_scale == "logarithmic" and column.x_min is not None and column.x_min <= 0:
                issues.append(
                    _issue(
                        "invalid_log_range",
                        PreflightSeverity.ERROR,
                        column=column.title,
                    )
                )
            for mnemonic in column.curve_mnemonics:
                mapped_id = curve_bindings.get(mnemonic)
                if mapped_id is None and dataset.curve_by_mnemonic(mnemonic) is None:
                    issues.append(
                        _issue(
                            "missing_curve",
                            PreflightSeverity.WARNING,
                            curve=mnemonic,
                            column=column.title,
                        )
                    )
    page_count = 0
    try:
        depth_pages = masterlog_page_ranges(template, session, settings)
        column_pages = masterlog_column_groups(template, page_size.width())
        page_count = max(1, len(depth_pages)) * max(1, len(column_pages))
    except MasterlogRenderError as exc:
        issues.append(_issue("render_blocked", PreflightSeverity.ERROR, error=str(exc)))
    return MasterlogPreflightReport(tuple(issues), page_count)


def _issue(code: str, severity: PreflightSeverity, **values: object) -> MasterlogPreflightIssue:
    return MasterlogPreflightIssue(code, severity, tuple(values.items()))
