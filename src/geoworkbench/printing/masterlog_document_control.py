from __future__ import annotations

from dataclasses import dataclass
from math import ceil

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


def masterlog_document_control_layout(
    template: MasterlogTemplate, session: ProjectSession | None,
    depth_range: tuple[float, float] | None, width_mm: float,
    language: AppLanguage = AppLanguage.RU,
) -> MasterlogDocumentControlLayout | None:
    saved = template_header_values(template)
    if session is None or not any(saved.get(field, "").strip() for field in DOCUMENT_CONTROL_HEADER_FIELDS):
        return None
    dataset = session.current_dataset
    unit = (dataset.active_index.unit or "м") if dataset is not None else ""
    interval = f"{depth_range[0]:g} — {depth_range[1]:g} {unit}".strip() if depth_range is not None else ""
    snapshot = form_report_document_control(session, template, language, title=template.name, interval=interval)
    rows = snapshot.available_rows + tuple(("", note) for note in snapshot.notes)
    columns = 2 if width_mm >= 160.0 else 1
    # Empty translations can intentionally suppress a context row. Reserve the
    # largest localized snapshot so size/pagination remain language independent.
    row_count = len(rows)
    for other_language in AppLanguage:
        other = form_report_document_control(session, template, other_language, title=template.name, interval=interval)
        row_count = max(row_count, len(other.available_rows) + len(other.notes))
    return MasterlogDocumentControlLayout(snapshot, columns, rows, 7.0 + ceil(row_count / columns) * 4.5)
