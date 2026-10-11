from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite
from numbers import Real

from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.printing.form_report_document_control import form_report_document_control
from geoworkbench.printing.header_fields import DOCUMENT_CONTROL_HEADER_FIELDS, template_header_values
from geoworkbench.printing.report_document_control import ReportDocumentControl
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class MasterlogDocumentControlLayout:
    snapshot: ReportDocumentControl
    columns: int
    rows: tuple[tuple[str, str], ...]
    height_mm: float
    footer_height_mm: float = 10.0
    row_height_mm: float = 4.5
    brand_height_mm: float = 5.0


def _finite_masterlog_value(value: object, name: str) -> float:
    """Keep invalid print geometry and depth labels out of Masterlog output."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    try:
        numeric = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not isfinite(numeric):
        raise ValueError(f"{name} must be a finite number")
    return numeric


def masterlog_document_control_layout(
    template: MasterlogTemplate, session: ProjectSession | None,
    depth_range: tuple[float, float] | None, width_mm: float,
    language: AppLanguage = AppLanguage.RU,
) -> MasterlogDocumentControlLayout | None:
    width = _finite_masterlog_value(width_mm, "width_mm")
    if width <= 0.0:
        raise ValueError("width_mm must be greater than zero")
    if depth_range is not None:
        top = _finite_masterlog_value(depth_range[0], "depth_top")
        bottom = _finite_masterlog_value(depth_range[1], "depth_bottom")
        if bottom < top:
            raise ValueError("Masterlog document-control depth range is reversed")
    saved = template_header_values(template)
    if session is None or not any(saved.get(field, "").strip() for field in DOCUMENT_CONTROL_HEADER_FIELDS):
        return None
    dataset = session.current_dataset
    unit = (dataset.active_index.unit or "м") if dataset is not None else ""
    interval = f"{depth_range[0]:g} — {depth_range[1]:g} {unit}".strip() if depth_range is not None else ""
    snapshot = form_report_document_control(session, template, language, title=template.name, interval=interval)
    rows = snapshot.available_rows + tuple(("", note) for note in snapshot.notes)
    columns = 2 if width >= 160.0 else 1
    # Empty translations can intentionally suppress a context row. Reserve the
    # largest localized snapshot so size/pagination remain language independent.
    row_count = len(rows)
    for other_language in AppLanguage:
        other = form_report_document_control(session, template, other_language, title=template.name, interval=interval)
        row_count = max(row_count, len(other.available_rows) + len(other.notes))
    return MasterlogDocumentControlLayout(snapshot, columns, rows, 7.0 + ceil(row_count / columns) * 4.5)
