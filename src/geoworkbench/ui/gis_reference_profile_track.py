"""Read-only MD track for a calibrated profile: exact points, not interpolation."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from PySide6.QtCore import QPointF, QRectF, QSize
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QPalette, QPen
from PySide6.QtWidgets import QWidget

from geoworkbench.services.gis_reference_calibration import (
    CalibratedGisProfile, GisProfileRowStatus,
)
from geoworkbench.services.localization import Localizer
from geoworkbench.services.petrophysical_reference_models import PetrophysicalQuality


@dataclass(frozen=True, slots=True)
class ProfileTrackPoint:
    """A single original row; a missing estimate has no horizontal coordinate."""

    row_index: int
    depth_fraction: float
    value_fraction: float | None
    status: GisProfileRowStatus
    quality: PetrophysicalQuality | None


@dataclass(frozen=True, slots=True)
class ProfileTrackProjection:
    value_bounds: tuple[float, float]
    points: tuple[ProfileTrackPoint, ...]


def _fraction(value: float, lower: float, upper: float) -> float:
    if lower == upper:
        return 0.5
    # Avoid overflow for finite opposite-signed extremes. The ordinary path
    # retains precision for adjacent floats at large positive MD.
    span = upper - lower
    if span == float("inf"):
        scale = max(abs(lower), abs(upper))
        return (value / scale - lower / scale) / (upper / scale - lower / scale)
    return (value - lower) / span


def project_profile_track(
    profile: CalibratedGisProfile, *,
    visible_md_bounds: tuple[float, float] | None = None,
) -> ProfileTrackProjection:
    """Project exact rows into the requested metre-MD viewport.

    The horizontal scale includes [0,1] and all actual profile outliers, so
    panning or zooming never changes the meaning of a plotted value. No lines
    join rows; their count or endpoints do not assert coverage. A singleton
    full-profile MD is shown at mid-height. Source order and row IDs persist.
    A viewport outside the calibrated interval contains no invented rows.
    """
    values = [row.estimate.value for row in profile.rows if row.estimate is not None]
    lower, upper = min(0.0, min(values, default=0.0)), max(1.0, max(values, default=1.0))
    top, base = profile.md_bounds if visible_md_bounds is None else visible_md_bounds
    if not (isfinite(top) and isfinite(base)) or top > base or (
        visible_md_bounds is not None and top == base
    ):
        raise ValueError("Profile viewport requires finite ordered MD bounds with positive span")
    points = tuple(
        ProfileTrackPoint(
            index, _fraction(row.md_m, top, base),
            _fraction(row.estimate.value, lower, upper) if row.estimate is not None else None,
            row.status, row.estimate.quality if row.estimate is not None else None,
        )
        for index, row in enumerate(profile.rows)
        if top <= row.md_m <= base
    )
    return ProfileTrackProjection((lower, upper), points)


class GisReferenceProfileTrack(QWidget):
    """QPainter value-only track, avoiding PlotItem/menu ownership and project edits."""

    def __init__(self, profile: CalibratedGisProfile, localizer: Localizer,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.profile = profile
        self.localizer = localizer
        self.projection = project_profile_track(profile)
        self._visible_md_bounds: tuple[float, float] | None = None
        self.selected_row: int | None = None
        self.setObjectName("gis-reference-profile-track")
        self.setMinimumSize(220, 180)
        self.setAccessibleName(localizer.text("petro_reference.profile_track_title"))

    def sizeHint(self) -> QSize:
        return QSize(340, 420)

    def set_visible_md_bounds(self, bounds: tuple[float, float] | None) -> None:
        """Set an explicit display window; None restores the whole profile.

        The caller must verify live source/axis before displaying a snapshot.
        Selection remains an original profile row, even when off-screen.
        """
        projection = project_profile_track(self.profile, visible_md_bounds=bounds)
        self._visible_md_bounds = bounds
        self.projection = projection
        self.update()

    def select_row(self, row: int | None) -> None:
        self.selected_row = row if row is not None and 0 <= row < len(self.profile.rows) else None
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        try:
            palette = self.palette()
            foreground = palette.color(QPalette.ColorRole.Text)
            muted = palette.color(QPalette.ColorRole.Mid)
            highlight = palette.color(QPalette.ColorRole.Highlight)
            painter.fillRect(self.rect(), palette.color(QPalette.ColorRole.Base))
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            metrics = painter.fontMetrics()
            line_height = float(metrics.height())
            top_md, base_md = (
                self.profile.md_bounds if self._visible_md_bounds is None else self._visible_md_bounds
            )
            top_text, base_text = format(top_md, ".9g"), format(base_md, ".9g")
            left = float(max(metrics.horizontalAdvance(top_text), metrics.horizontalAdvance(base_text))) + 22
            plot = QRectF(left, line_height * 2 + 12, max(1.0, self.width() - left - 14),
                          max(1.0, self.height() - line_height * 4 - 24))
            painter.setPen(foreground)
            painter.drawText(QPointF(8, line_height), self.localizer.text("petro_reference.profile_track_title"))
            lower, upper = self.projection.value_bounds
            low_text, high_text = format(lower, ".6g"), format(upper, ".6g")
            painter.drawText(QPointF(plot.left(), plot.top() - 5), low_text)
            painter.drawText(QPointF(plot.right() - metrics.horizontalAdvance(high_text), plot.top() - 5), high_text)
            painter.drawText(QPointF(8, plot.top() + line_height), top_text)
            if top_md != base_md:
                painter.drawText(QPointF(8, plot.bottom()), base_text)
            painter.drawText(QPointF(8, self.height() - 7),
                             self.localizer.text("petro_reference.profile_track_axis"))
            painter.setPen(QPen(muted, 1.0))
            painter.drawRect(plot)
            for reference in (0.0, 1.0):
                x = plot.left() + _fraction(reference, lower, upper) * plot.width()
                painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            selected_point = next(
                (point for point in self.projection.points if point.row_index == self.selected_row), None,
            )
            if selected_point is not None:
                y = plot.top() + selected_point.depth_fraction * plot.height()
                pen = QPen(highlight, 1.5)
                painter.setPen(pen)
                painter.drawLine(QPointF(plot.left() - 14, y), QPointF(plot.right(), y))
            for point in self.projection.points:
                y = plot.top() + point.depth_fraction * plot.height()
                if point.value_fraction is None:
                    # Marks in a separate gutter, never at x=0 or a fabricated value.
                    x = plot.left() - 9
                    painter.setPen(QPen(muted, 1.8))
                    painter.drawLine(QPointF(x - 3, y), QPointF(x + 3, y))
                    if point.status is GisProfileRowStatus.INVALID_MEASUREMENT:
                        painter.drawLine(QPointF(x, y - 3), QPointF(x, y + 3))
                    continue
                x = plot.left() + point.value_fraction * plot.width()
                if point.quality is PetrophysicalQuality.VALID:
                    painter.setPen(QPen(foreground, 1.8))
                    painter.drawEllipse(QPointF(x, y), 2.5, 2.5)
                else:
                    painter.setPen(QPen(QColor("#d97706"), 2.0))
                    painter.drawLine(QPointF(x - 3, y - 3), QPointF(x + 3, y + 3))
                    painter.drawLine(QPointF(x - 3, y + 3), QPointF(x + 3, y - 3))
            if not self.projection.points:
                painter.setPen(foreground)
                painter.drawText(QPointF(plot.left() + 4, plot.center().y()),
                                 self.localizer.text("petro_reference.profile_track_empty"))
        finally:
            painter.end()
