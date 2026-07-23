from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, radians, sin

from geoworkbench.project.annotation_schema import AnnotationKind, AnnotationRecord


@dataclass(frozen=True, slots=True)
class LayoutPoint:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class LayoutRect:
    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def center(self) -> LayoutPoint:
        return LayoutPoint(self.left + self.width / 2.0, self.top + self.height / 2.0)

    def contains(self, point: LayoutPoint) -> bool:
        return self.left <= point.x <= self.right and self.top <= point.y <= self.bottom


@dataclass(frozen=True, slots=True)
class AnnotationLayout:
    anchor: LayoutPoint
    box: LayoutRect
    leader_endpoint: LayoutPoint | None


def annotation_box_rect(
    record: AnnotationRecord,
    *,
    anchor_x: float = 0.0,
    anchor_y: float = 0.0,
    pixel_scale: float = 1.0,
    max_width: float | None = None,
    max_height: float | None = None,
) -> LayoutRect:
    """Return the annotation box in a surface coordinate system.

    Persisted annotation geometry is defined in reference pixels.  Screen uses
    ``pixel_scale=1``; print/PDF uses ``25.4 / 96`` millimetres per reference
    pixel.  Keeping this conversion here prevents screen and print from growing
    independent minimum-size or offset rules.
    """

    scale = _positive_finite(pixel_scale, "pixel_scale")
    width = max(40.0, float(record.width)) * scale
    height = max(24.0, float(record.height)) * scale
    if max_width is not None:
        width = min(width, _positive_finite(max_width, "max_width"))
    if max_height is not None:
        height = min(height, _positive_finite(max_height, "max_height"))
    return LayoutRect(
        float(anchor_x) + float(record.offset_x) * scale,
        float(anchor_y) + float(record.offset_y) * scale,
        width,
        height,
    )


def layout_annotation(
    record: AnnotationRecord,
    *,
    anchor_x: float,
    anchor_y: float,
    bounds: LayoutRect | None = None,
    pixel_scale: float = 1.0,
    visible_margin: float | None = None,
    max_width: float | None = None,
    max_height: float | None = None,
) -> AnnotationLayout:
    """Resolve a deterministic screen/print box and leader endpoint."""

    anchor = LayoutPoint(float(anchor_x), float(anchor_y))
    box = annotation_box_rect(
        record,
        anchor_x=anchor.x,
        anchor_y=anchor.y,
        pixel_scale=pixel_scale,
        max_width=max_width,
        max_height=max_height,
    )
    if bounds is not None:
        margin = (
            20.0 * float(pixel_scale)
            if visible_margin is None
            else _positive_finite(visible_margin, "visible_margin")
        )
        margin = min(margin, box.width, box.height)
        left = min(
            max(box.left, bounds.left - box.width + margin),
            bounds.right - margin,
        )
        top = min(
            max(box.top, bounds.top - box.height + margin),
            bounds.bottom - margin,
        )
        box = LayoutRect(left, top, box.width, box.height)
    endpoint = None
    if record.kind in {AnnotationKind.CALLOUT, AnnotationKind.VALUE}:
        endpoint = annotation_leader_endpoint(
            anchor,
            box,
            rotation_degrees=float(record.style.rotation),
        )
    return AnnotationLayout(anchor=anchor, box=box, leader_endpoint=endpoint)


def annotation_leader_endpoint(
    anchor: LayoutPoint,
    box: LayoutRect,
    *,
    rotation_degrees: float = 0.0,
) -> LayoutPoint:
    """Return the closest point on a possibly rotated box to the anchor."""

    rotation = float(rotation_degrees)
    if not isfinite(rotation):
        rotation = 0.0
    center = box.center
    local_anchor = _rotate(anchor, center, -rotation)
    x = min(max(local_anchor.x, box.left), box.right)
    y = min(max(local_anchor.y, box.top), box.bottom)
    if box.contains(local_anchor):
        distances = (
            (abs(local_anchor.x - box.left), LayoutPoint(box.left, local_anchor.y)),
            (abs(local_anchor.x - box.right), LayoutPoint(box.right, local_anchor.y)),
            (abs(local_anchor.y - box.top), LayoutPoint(local_anchor.x, box.top)),
            (abs(local_anchor.y - box.bottom), LayoutPoint(local_anchor.x, box.bottom)),
        )
        endpoint = min(distances, key=lambda item: item[0])[1]
    else:
        endpoint = LayoutPoint(x, y)
    return _rotate(endpoint, center, rotation)


def _rotate(point: LayoutPoint, center: LayoutPoint, angle_degrees: float) -> LayoutPoint:
    if not angle_degrees:
        return point
    angle = radians(angle_degrees)
    dx = point.x - center.x
    dy = point.y - center.y
    return LayoutPoint(
        center.x + dx * cos(angle) - dy * sin(angle),
        center.y + dx * sin(angle) + dy * cos(angle),
    )


def _positive_finite(value: float, name: str) -> float:
    normalized = float(value)
    if not isfinite(normalized) or normalized <= 0.0:
        raise ValueError(f"{name} must be a finite positive number")
    return normalized
