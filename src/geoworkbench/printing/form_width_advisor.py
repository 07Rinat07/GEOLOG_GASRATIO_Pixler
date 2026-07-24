from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Iterable


DEFAULT_SCREEN_DPI = 96.0
A4_PORTRAIT_WIDTH_MM = 210.0
A4_LANDSCAPE_WIDTH_MM = 297.0
DEFAULT_HORIZONTAL_MARGINS_MM = 20.0
DEFAULT_COLUMN_SPACING_PX = 2


class FormWidthLevel(StrEnum):
    FITS_PORTRAIT = "fits_portrait"
    FITS_LANDSCAPE = "fits_landscape"
    NEEDS_FIT = "needs_fit"
    NEEDS_SPLIT = "needs_split"


@dataclass(frozen=True, slots=True)
class FormWidthAudit:
    visible_columns: int
    total_width_px: int
    total_width_mm: float
    portrait_capacity_px: int
    landscape_capacity_px: int
    portrait_scale_percent: float
    landscape_scale_percent: float
    level: FormWidthLevel

    @property
    def portrait_overflow_px(self) -> int:
        return max(0, self.total_width_px - self.portrait_capacity_px)

    @property
    def landscape_overflow_px(self) -> int:
        return max(0, self.total_width_px - self.landscape_capacity_px)

    @property
    def portrait_pages_at_actual_size(self) -> int:
        if self.portrait_capacity_px <= 0:
            return 1
        return max(1, (self.total_width_px + self.portrait_capacity_px - 1) // self.portrait_capacity_px)


def px_to_mm(value_px: int | float, *, dpi: float = DEFAULT_SCREEN_DPI) -> float:
    _validate_dpi(dpi)
    if isinstance(value_px, bool) or not isinstance(value_px, (int, float)):
        raise ValueError("Ширина должна быть числом")
    if not isfinite(float(value_px)) or float(value_px) < 0:
        raise ValueError("Ширина не может быть отрицательной")
    return float(value_px) * 25.4 / float(dpi)


def mm_to_px(value_mm: int | float, *, dpi: float = DEFAULT_SCREEN_DPI) -> int:
    _validate_dpi(dpi)
    if isinstance(value_mm, bool) or not isinstance(value_mm, (int, float)):
        raise ValueError("Физическая ширина должна быть числом")
    if not isfinite(float(value_mm)) or float(value_mm) <= 0:
        raise ValueError("Физическая ширина должна быть положительной")
    return max(1, round(float(value_mm) / 25.4 * float(dpi)))


def audit_form_width(
    widths: Iterable[int],
    *,
    spacing_px: int = DEFAULT_COLUMN_SPACING_PX,
    dpi: float = DEFAULT_SCREEN_DPI,
    horizontal_margins_mm: float = DEFAULT_HORIZONTAL_MARGINS_MM,
) -> FormWidthAudit:
    normalized = tuple(widths)
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in normalized
    ):
        raise ValueError("Ширины колонок должны быть неотрицательными целыми числами")
    if isinstance(spacing_px, bool) or not isinstance(spacing_px, int) or spacing_px < 0:
        raise ValueError("Интервал между колонками должен быть неотрицательным целым")
    _validate_dpi(dpi)
    if (
        isinstance(horizontal_margins_mm, bool)
        or not isinstance(horizontal_margins_mm, (int, float))
        or not isfinite(float(horizontal_margins_mm))
        or not 0 <= float(horizontal_margins_mm) < A4_PORTRAIT_WIDTH_MM
    ):
        raise ValueError("Суммарные горизонтальные поля A4 заданы неверно")

    visible_columns = sum(1 for value in normalized if value > 0)
    positive = tuple(value for value in normalized if value > 0)
    total_width_px = sum(positive) + spacing_px * max(0, visible_columns - 1)
    portrait_capacity_px = mm_to_px(
        A4_PORTRAIT_WIDTH_MM - float(horizontal_margins_mm), dpi=dpi
    )
    landscape_capacity_px = mm_to_px(
        A4_LANDSCAPE_WIDTH_MM - float(horizontal_margins_mm), dpi=dpi
    )
    portrait_scale = (
        min(100.0, portrait_capacity_px / total_width_px * 100.0)
        if total_width_px > 0
        else 100.0
    )
    landscape_scale = (
        min(100.0, landscape_capacity_px / total_width_px * 100.0)
        if total_width_px > 0
        else 100.0
    )
    if total_width_px <= portrait_capacity_px:
        level = FormWidthLevel.FITS_PORTRAIT
    elif total_width_px <= landscape_capacity_px:
        level = FormWidthLevel.FITS_LANDSCAPE
    elif landscape_scale >= 70.0:
        level = FormWidthLevel.NEEDS_FIT
    else:
        level = FormWidthLevel.NEEDS_SPLIT
    return FormWidthAudit(
        visible_columns=visible_columns,
        total_width_px=total_width_px,
        total_width_mm=px_to_mm(total_width_px, dpi=dpi),
        portrait_capacity_px=portrait_capacity_px,
        landscape_capacity_px=landscape_capacity_px,
        portrait_scale_percent=portrait_scale,
        landscape_scale_percent=landscape_scale,
        level=level,
    )


def _validate_dpi(dpi: float) -> None:
    if (
        isinstance(dpi, bool)
        or not isinstance(dpi, (int, float))
        or not isfinite(float(dpi))
        or not 72.0 <= float(dpi) <= 600.0
    ):
        raise ValueError("DPI должен находиться в диапазоне 72–600")
