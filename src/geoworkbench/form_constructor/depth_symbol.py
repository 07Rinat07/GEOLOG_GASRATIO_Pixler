from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class DepthSymbolPlacement:
    """Semantic placement of a symbol on a depth-oriented form.

    `depth` remains the source of truth.  Manual movement is stored as an offset in
    millimetres, so changing page size or depth scale does not detach the symbol from
    the geological event it represents.
    """

    symbol_id: str
    depth: float
    bottom_depth: float | None = None
    track_id: str | None = None
    parameter_id: str | None = None
    label: str = ""
    offset_x_mm: float = 0.0
    offset_y_mm: float = 0.0
    width_mm: float = 4.0
    height_mm: float = 4.0
    preserve_aspect_ratio: bool = True

    def __post_init__(self) -> None:
        if not self.symbol_id.strip():
            raise ValueError("symbol_id must not be empty")
        if self.bottom_depth is not None and self.bottom_depth < self.depth:
            raise ValueError("bottom_depth must be greater than or equal to depth")
        if self.width_mm <= 0 or self.height_mm <= 0:
            raise ValueError("symbol size must be positive")

    def with_manual_offset(self, x_mm: float, y_mm: float) -> "DepthSymbolPlacement":
        return replace(self, offset_x_mm=float(x_mm), offset_y_mm=float(y_mm))

    def page_y_mm(self, *, page_top_depth: float, millimetres_per_depth_unit: float) -> float:
        if millimetres_per_depth_unit <= 0:
            raise ValueError("millimetres_per_depth_unit must be positive")
        return (self.depth - page_top_depth) * millimetres_per_depth_unit + self.offset_y_mm

    def interval_height_mm(self, *, millimetres_per_depth_unit: float) -> float | None:
        if self.bottom_depth is None:
            return None
        if millimetres_per_depth_unit <= 0:
            raise ValueError("millimetres_per_depth_unit must be positive")
        return (self.bottom_depth - self.depth) * millimetres_per_depth_unit
