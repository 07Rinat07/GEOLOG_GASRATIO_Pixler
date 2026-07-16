from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.masterlog_renderer import (
    MasterlogRenderError,
    masterlog_column_groups,
    masterlog_page_ranges,
    masterlog_page_size_mm,
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
        return tuple(
            issue for issue in self.issues if issue.severity is PreflightSeverity.WARNING
        )


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
    if dataset is not None:
        for column in template.columns:
            if (
                column.x_scale == "logarithmic"
                and column.x_min is not None
                and column.x_min <= 0
            ):
                issues.append(
                    _issue(
                        "invalid_log_range",
                        PreflightSeverity.ERROR,
                        column=column.title,
                    )
                )
            for mnemonic in column.curve_mnemonics:
                if dataset.curve_by_mnemonic(mnemonic) is None:
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
        issues.append(
            _issue("render_blocked", PreflightSeverity.ERROR, error=str(exc))
        )
    return MasterlogPreflightReport(tuple(issues), page_count)


def _issue(
    code: str, severity: PreflightSeverity, **values: object
) -> MasterlogPreflightIssue:
    return MasterlogPreflightIssue(code, severity, tuple(values.items()))
