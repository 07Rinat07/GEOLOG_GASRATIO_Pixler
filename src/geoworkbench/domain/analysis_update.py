"""Typed immutable records for WELL-02 late-analysis updates."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
import re


class AnalysisField(StrEnum):
    """Analysis-owned fields that may be populated by a late result."""

    LBA_GROUP = "lba_group"
    LBA_TYPE_ID = "lba_type_id"
    LBA_INTENSITY = "lba_intensity"
    LBA_COLOR = "lba_color"
    LBA_DISTRIBUTION = "lba_distribution"
    LBA_CUT = "lba_cut"
    LBA_CUT_SPEED = "lba_cut_speed"
    LBA_CUT_COLOR = "lba_cut_color"
    LBA_RESIDUE_TYPE = "lba_residue_type"
    LBA_RESIDUE_COLOR = "lba_residue_color"
    LBA_ODOUR = "lba_odour"
    LBA_STAIN = "lba_stain"
    LBA_DESCRIPTION = "lba_description"
    CALCITE_PERCENT = "calcite_percent"
    DOLOMITE_PERCENT = "dolomite_percent"
    ANALYSIS_INTERPRETATION = "analysis_interpretation"


AnalysisScalar = int | float | str


@dataclass(frozen=True, slots=True)
class AnalysisCellChange:
    sample_id: str
    top_depth: float
    bottom_depth: float
    field: AnalysisField
    old_value: AnalysisScalar | None
    new_value: AnalysisScalar

    def __post_init__(self) -> None:
        if not isinstance(self.sample_id, str) or not self.sample_id.strip():
            raise ValueError("sample_id анализа должен быть непустой строкой")
        if len(self.sample_id) > 2000:
            raise ValueError("sample_id анализа слишком длинный")
        if isinstance(self.top_depth, bool) or isinstance(self.bottom_depth, bool):
            raise ValueError("Границы анализа должны быть числами")
        if not isfinite(float(self.top_depth)) or not isfinite(float(self.bottom_depth)):
            raise ValueError("Границы анализа должны быть конечными")
        if float(self.bottom_depth) <= float(self.top_depth):
            raise ValueError("Нижняя граница анализа должна быть больше верхней")
        if not isinstance(self.field, AnalysisField):
            raise ValueError("Неизвестное поле анализа")
        _validate_scalar(self.old_value, allow_none=True)
        _validate_scalar(self.new_value, allow_none=False)


@dataclass(frozen=True, slots=True)
class AnalysisUpdateRecord:
    update_id: str
    well_id: str
    source_name: str
    source_sha256: str
    imported_at: str
    selected_fields: tuple[AnalysisField, ...]
    changes: tuple[AnalysisCellChange, ...]
    well_sha256_before: str
    well_sha256_after: str

    def __post_init__(self) -> None:
        for value, label in (
            (self.update_id, "update_id"),
            (self.well_id, "well_id"),
            (self.source_name, "source_name"),
            (self.imported_at, "imported_at"),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > 2000:
                raise ValueError(f"Некорректное поле {label} истории анализа")
        for digest in (self.source_sha256, self.well_sha256_before, self.well_sha256_after):
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Некорректный SHA-256 истории анализа")
        if (
            not isinstance(self.selected_fields, tuple)
            or not self.selected_fields
            or len(set(self.selected_fields)) != len(self.selected_fields)
            or not all(isinstance(item, AnalysisField) for item in self.selected_fields)
        ):
            raise ValueError("Некорректный набор полей истории анализа")
        if (
            not isinstance(self.changes, tuple)
            or not self.changes
            or len(self.changes) > 10_000
            or not all(isinstance(item, AnalysisCellChange) for item in self.changes)
        ):
            raise ValueError("Некорректный список изменений анализа")
        identities = [(item.sample_id, item.field) for item in self.changes]
        if len(set(identities)) != len(identities):
            raise ValueError("История анализа содержит повтор одного поля образца")
        allowed = set(self.selected_fields)
        if any(item.field not in allowed for item in self.changes):
            raise ValueError("История анализа содержит невыбранное поле")
        if any(not _is_empty(item.old_value) for item in self.changes):
            raise ValueError("Late-analysis history допускает только fill-only изменения")


def _validate_scalar(value: AnalysisScalar | None, *, allow_none: bool) -> None:
    if value is None:
        if allow_none:
            return
        raise ValueError("Новое значение анализа не может быть null")
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("Значение анализа должно быть числом или строкой")
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("Числовое значение анализа должно быть конечным")
    if isinstance(value, str) and len(value) > 20_000:
        raise ValueError("Текст анализа слишком длинный")


def _is_empty(value: AnalysisScalar | None) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())
