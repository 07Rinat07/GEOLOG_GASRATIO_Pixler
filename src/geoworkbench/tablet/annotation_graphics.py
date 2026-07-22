from __future__ import annotations

from math import atan2, cos, pi, sin

from PySide6.QtCore import QLineF, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsSceneContextMenuEvent,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from geoworkbench.project.annotation_schema import AnnotationKind, AnnotationRecord


class TabletAnnotationItem(QGraphicsObject):
    """Device-sized annotation anchored to a plot data point.

    The anchor follows depth/time/curve coordinates in the ViewBox while the
    callout box keeps a predictable physical screen size. The same QGraphicsItem
    is rendered by QWidget/PDF/print capture, preventing screen/print drift.
    """

    edit_requested = Signal(str)
    delete_requested = Signal(str)
    duplicate_requested = Signal(str)
    context_requested = Signal(str, QPoint)
    geometry_changed = Signal(str, float, float, float, float)

    HANDLE_SIZE = 14.0

    def __init__(
        self,
        record: AnnotationRecord,
        *,
        pixmap: QPixmap | None = None,
        edit_mode: bool = False,
        print_mode: bool = False,
    ) -> None:
        super().__init__()
        self.record = record
        self._pixmap = QPixmap(pixmap) if pixmap is not None else QPixmap()
        self._edit_mode = bool(edit_mode)
        self._print_mode = bool(print_mode)
        self._selected = False
        self._drag_mode: str | None = None
        self._press_screen = QPointF()
        self._start_geometry = (
            record.offset_x,
            record.offset_y,
            record.width,
            record.height,
        )
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)
        self.setAcceptHoverEvents(True)
        self.setZValue(9_500.0)
        self._apply_visibility()

    @property
    def annotation_id(self) -> str:
        return self.record.annotation_id

    @property
    def edit_mode(self) -> bool:
        return self._edit_mode and not self._print_mode

    def set_record(self, record: AnnotationRecord, pixmap: QPixmap | None = None) -> None:
        self.prepareGeometryChange()
        self.record = record
        if pixmap is not None:
            self._pixmap = QPixmap(pixmap)
        self._apply_visibility()
        self.update()

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = bool(enabled)
        self.update()

    def set_print_mode(self, enabled: bool) -> None:
        self._print_mode = bool(enabled)
        self._apply_visibility()

    def _apply_visibility(self) -> None:
        self.setVisible(
            self.record.visible and (not self._print_mode or self.record.print_enabled)
        )

    def box_rect(self) -> QRectF:
        return QRectF(
            float(self.record.offset_x),
            float(self.record.offset_y),
            max(40.0, float(self.record.width)),
            max(24.0, float(self.record.height)),
        )

    def resize_handle_rect(self) -> QRectF:
        rect = self.box_rect()
        return QRectF(
            rect.right() - self.HANDLE_SIZE,
            rect.bottom() - self.HANDLE_SIZE,
            self.HANDLE_SIZE,
            self.HANDLE_SIZE,
        )

    def _box_transform(self) -> QTransform:
        transform = QTransform()
        rotation = float(self.record.style.rotation)
        if rotation:
            center = self.box_rect().center()
            transform.translate(center.x(), center.y())
            transform.rotate(rotation)
            transform.translate(-center.x(), -center.y())
        return transform

    def _box_shape(self) -> QPainterPath:
        path = QPainterPath()
        radius = max(0.0, float(self.record.style.corner_radius))
        path.addRoundedRect(self.box_rect(), radius, radius)
        if self.record.style.rotation:
            return self._box_transform().map(path)
        return path

    def _point_in_box_coordinates(self, point: QPointF) -> QPointF:
        if not self.record.style.rotation:
            return point
        inverse, invertible = self._box_transform().inverted()
        return inverse.map(point) if invertible else point

    def boundingRect(self) -> QRectF:  # noqa: N802
        blur = max(12.0, float(self.record.style.shadow_blur) + 8.0)
        rect = self._box_shape().boundingRect().adjusted(-blur, -blur, blur, blur)
        if self._has_leader():
            rect = rect.united(
                QRectF(QPointF(0.0, 0.0), self._leader_end()).normalized()
            )
            rect = rect.adjusted(-12.0, -12.0, 12.0, 12.0)
        return rect

    def shape(self) -> QPainterPath:
        path = self._box_shape()
        if self._has_leader():
            pen_width = max(8.0, self.record.style.leader_width + 6.0)
            corridor = QPainterPath()
            # A broad rectangular corridor is sufficient for intuitive hit testing.
            line_rect = QRectF(QPointF(0.0, 0.0), self._leader_end()).normalized()
            corridor.addRect(
                line_rect.adjusted(-pen_width, -pen_width, pen_width, pen_width)
            )
            path = path.united(corridor)
        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del option, widget
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._has_leader():
            self._paint_leader(painter)
        self._paint_box(painter)
        if self._edit_mode and not self.record.locked and not self._print_mode:
            self._paint_edit_handles(painter)
        painter.restore()

    def _paint_leader(self, painter: QPainter) -> None:
        style = self.record.style
        pen = QPen(QColor(style.leader_color), style.leader_width)
        pen.setStyle(_pen_style(style.leader_style))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        endpoint = self._leader_end()
        painter.drawLine(QLineF(QPointF(0.0, 0.0), endpoint))
        self._paint_arrow(painter, endpoint)

    def _paint_arrow(self, painter: QPainter, endpoint: QPointF) -> None:
        arrow_style = self.record.style.arrow_style
        if arrow_style == "none":
            return
        angle = atan2(endpoint.y(), endpoint.x())
        size = max(6.0, 4.0 + self.record.style.leader_width * 2.0)
        # Arrow belongs to the anchor point and points towards the callout box.
        first = QPointF(size * cos(angle - pi / 6.0), size * sin(angle - pi / 6.0))
        second = QPointF(size * cos(angle + pi / 6.0), size * sin(angle + pi / 6.0))
        color = QColor(self.record.style.leader_color)
        painter.save()
        if arrow_style == "circle":
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(0.0, 0.0), size / 2.5, size / 2.5)
        elif arrow_style == "open":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QLineF(QPointF(0.0, 0.0), first))
            painter.drawLine(QLineF(QPointF(0.0, 0.0), second))
        else:
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(QPolygonF([QPointF(0.0, 0.0), first, second]))
        painter.restore()

    def _paint_box(self, painter: QPainter) -> None:
        record = self.record
        style = record.style
        rect = self.box_rect()
        painter.save()
        if style.rotation:
            painter.translate(rect.center())
            painter.rotate(style.rotation)
            painter.translate(-rect.center())
        if style.shadow:
            shadow_rect = rect.translated(style.shadow_offset_x, style.shadow_offset_y)
            shadow = QColor(15, 23, 42, min(110, int(30 + style.shadow_blur * 5)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow)
            painter.drawRoundedRect(shadow_rect, style.corner_radius, style.corner_radius)
        fill = QColor(style.fill_color)
        fill.setAlphaF(style.fill_opacity)
        border = QPen(QColor(style.border_color), style.border_width)
        border.setStyle(_pen_style(style.border_style))
        painter.setPen(border if style.border_width > 0 else Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, style.corner_radius, style.corner_radius)

        content = rect.adjusted(style.padding, style.padding, -style.padding, -style.padding)
        if (
            record.kind in {AnnotationKind.IMAGE, AnnotationKind.SYMBOL}
            and not self._pixmap.isNull()
        ):
            self._paint_image_content(painter, content)
        else:
            self._paint_text_content(painter, content)
        painter.restore()

    def _paint_image_content(self, painter: QPainter, content: QRectF) -> None:
        caption_height = 0.0
        if self.record.text:
            caption_height = min(32.0, max(18.0, self.record.style.font_size * 1.8))
        image_rect = content.adjusted(0.0, 0.0, 0.0, -caption_height)
        source = QRectF(self._pixmap.rect())
        if source.width() > 0 and source.height() > 0 and image_rect.isValid():
            ratio = min(image_rect.width() / source.width(), image_rect.height() / source.height())
            width = source.width() * ratio
            height = source.height() * ratio
            target = QRectF(
                image_rect.center().x() - width / 2.0,
                image_rect.center().y() - height / 2.0,
                width,
                height,
            )
            painter.drawPixmap(target, self._pixmap, source)
        if caption_height > 0:
            caption_rect = QRectF(
                content.left(), content.bottom() - caption_height, content.width(), caption_height
            )
            self._paint_text_content(painter, caption_rect)

    def _paint_text_content(self, painter: QPainter, content: QRectF) -> None:
        style = self.record.style
        font = QFont(style.font_family)
        font.setPointSizeF(style.font_size)
        font.setBold(style.bold)
        font.setItalic(style.italic)
        font.setUnderline(style.underline)
        painter.setFont(font)
        painter.setPen(QColor(style.text_color))
        flags = Qt.TextFlag.TextWordWrap
        flags |= {
            "left": Qt.AlignmentFlag.AlignLeft,
            "center": Qt.AlignmentFlag.AlignHCenter,
            "right": Qt.AlignmentFlag.AlignRight,
        }[style.alignment]
        flags |= {
            "top": Qt.AlignmentFlag.AlignTop,
            "center": Qt.AlignmentFlag.AlignVCenter,
            "bottom": Qt.AlignmentFlag.AlignBottom,
        }[style.vertical_alignment]
        painter.drawText(content, int(flags), self.record.text)

    def _paint_edit_handles(self, painter: QPainter) -> None:
        painter.save()
        rect = self.box_rect()
        if self.record.style.rotation:
            painter.translate(rect.center())
            painter.rotate(self.record.style.rotation)
            painter.translate(-rect.center())
        selection_color = QColor("#2563eb")
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(selection_color, 1.0, Qt.PenStyle.DashLine))
        painter.drawRect(rect.adjusted(-3.0, -3.0, 3.0, 3.0))
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(selection_color, 1.5))
        painter.drawRect(self.resize_handle_rect())
        painter.restore()

    def _has_leader(self) -> bool:
        return self.record.kind in {AnnotationKind.CALLOUT, AnnotationKind.VALUE}

    def _leader_end(self) -> QPointF:
        rect = self.box_rect()
        transform = self._box_transform()
        inverse, invertible = transform.inverted()
        anchor = inverse.map(QPointF(0.0, 0.0)) if invertible else QPointF(0.0, 0.0)
        x = min(max(anchor.x(), rect.left()), rect.right())
        y = min(max(anchor.y(), rect.top()), rect.bottom())
        # If the anchor projects inside the box, attach to the closest edge.
        if rect.contains(anchor):
            distances = {
                "left": abs(anchor.x() - rect.left()),
                "right": abs(anchor.x() - rect.right()),
                "top": abs(anchor.y() - rect.top()),
                "bottom": abs(anchor.y() - rect.bottom()),
            }
            edge = min(distances, key=distances.get)
            if edge == "left":
                endpoint = QPointF(rect.left(), anchor.y())
            elif edge == "right":
                endpoint = QPointF(rect.right(), anchor.y())
            elif edge == "top":
                endpoint = QPointF(anchor.x(), rect.top())
            else:
                endpoint = QPointF(anchor.x(), rect.bottom())
        else:
            endpoint = QPointF(x, y)
        return transform.map(endpoint)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._edit_mode
            and not self.record.locked
            and not self._print_mode
        ):
            self._selected = True
            self.setSelected(True)
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._press_screen = QPointF(event.screenPos())
            self._start_geometry = (
                self.record.offset_x,
                self.record.offset_y,
                self.record.width,
                self.record.height,
            )
            box_point = self._point_in_box_coordinates(event.pos())
            self._drag_mode = (
                "resize" if self.resize_handle_rect().contains(box_point) else "move"
            )
            self.setCursor(
                Qt.CursorShape.SizeFDiagCursor
                if self._drag_mode == "resize"
                else Qt.CursorShape.SizeAllCursor
            )
            event.accept()
            self.update()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._drag_mode is None:
            super().mouseMoveEvent(event)
            return
        delta = QPointF(event.screenPos()) - self._press_screen
        offset_x, offset_y, width, height = self._start_geometry
        self.prepareGeometryChange()
        if self._drag_mode == "move":
            offset_x += delta.x()
            offset_y += delta.y()
        else:
            resize_delta = delta
            if self.record.style.rotation:
                angle = -float(self.record.style.rotation) * pi / 180.0
                resize_delta = QPointF(
                    delta.x() * cos(angle) - delta.y() * sin(angle),
                    delta.x() * sin(angle) + delta.y() * cos(angle),
                )
            width = max(40.0, width + resize_delta.x())
            height = max(24.0, height + resize_delta.y())
        self.record = AnnotationRecord(
            annotation_id=self.record.annotation_id,
            kind=self.record.kind,
            anchor=self.record.anchor,
            text=self.record.text,
            track_id=self.record.track_id,
            depth=self.record.depth,
            axis_value=self.record.axis_value,
            axis_id=self.record.axis_id,
            parameter_mnemonic=self.record.parameter_mnemonic,
            parameter_value=self.record.parameter_value,
            unit=self.record.unit,
            x_fraction=self.record.x_fraction,
            offset_x=offset_x,
            offset_y=offset_y,
            width=width,
            height=height,
            style=self.record.style,
            asset_ref=self.record.asset_ref,
            visible=self.record.visible,
            locked=self.record.locked,
            print_enabled=self.record.print_enabled,
        )
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._drag_mode is None:
            super().mouseReleaseEvent(event)
            return
        self._drag_mode = None
        self.unsetCursor()
        self.geometry_changed.emit(
            self.annotation_id,
            self.record.offset_x,
            self.record.offset_y,
            self.record.width,
            self.record.height,
        )
        event.accept()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._edit_mode
            and not self._print_mode
        ):
            self.edit_requested.emit(self.annotation_id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self._selected = False
        self.setSelected(False)
        self.update()
        super().focusOutEvent(event)

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent) -> None:  # noqa: N802
        if self._edit_mode and not self._print_mode:
            self.context_requested.emit(self.annotation_id, event.screenPos())
            event.accept()
            return
        event.ignore()

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        box_point = self._point_in_box_coordinates(event.pos())
        if (
            self._edit_mode
            and not self.record.locked
            and self.resize_handle_rect().contains(box_point)
        ):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif (
            self._edit_mode
            and not self.record.locked
            and self.box_rect().contains(box_point)
        ):
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.unsetCursor()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        if self._drag_mode is None:
            self.unsetCursor()
        super().hoverLeaveEvent(event)


def _pen_style(value: str) -> Qt.PenStyle:
    return {
        "dash": Qt.PenStyle.DashLine,
        "dot": Qt.PenStyle.DotLine,
    }.get(value, Qt.PenStyle.SolidLine)
