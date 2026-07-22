from __future__ import annotations

from dataclasses import replace
from math import atan2, cos, pi, sin

from PySide6.QtCore import QLineF, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
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
from geoworkbench.tablet.annotation_interaction import (
    keep_annotation_reachable,
    resize_annotation_geometry,
)


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
        """Backward-compatible alias for the south-east resize handle."""

        return self.resize_handle_rects()["se"]

    def resize_handle_rects(self) -> dict[str, QRectF]:
        """Return eight analogue-style resize handles around the text box."""

        rect = self.box_rect()
        size = self.HANDLE_SIZE
        half = size / 2.0
        return {
            "nw": QRectF(rect.left() - half, rect.top() - half, size, size),
            "n": QRectF(rect.center().x() - half, rect.top() - half, size, size),
            "ne": QRectF(rect.right() - half, rect.top() - half, size, size),
            "e": QRectF(rect.right() - half, rect.center().y() - half, size, size),
            "se": QRectF(rect.right() - half, rect.bottom() - half, size, size),
            "s": QRectF(rect.center().x() - half, rect.bottom() - half, size, size),
            "sw": QRectF(rect.left() - half, rect.bottom() - half, size, size),
            "w": QRectF(rect.left() - half, rect.center().y() - half, size, size),
        }

    def resize_handle_at(self, point: QPointF) -> str | None:
        local = self._point_in_box_coordinates(point)
        for handle, rect in self.resize_handle_rects().items():
            if rect.contains(local):
                return handle
        return None

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
            leader = QPainterPath(QPointF(0.0, 0.0))
            leader.lineTo(self._leader_end())
            stroker = QPainterPathStroker()
            stroker.setWidth(max(10.0, self.record.style.leader_width + 8.0))
            stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
            path = path.united(stroker.createStroke(leader))
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
        if (
            self._edit_mode
            and self._selected
            and not self.record.locked
            and not self._print_mode
        ):
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
        for handle in self.resize_handle_rects().values():
            painter.drawRect(handle)
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
            handle = self.resize_handle_at(event.pos())
            self._drag_mode = handle or "move"
            self.setCursor(_cursor_for_handle(handle) if handle else Qt.CursorShape.SizeAllCursor)
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
            resize_delta = _unrotate_delta(delta, self.record.style.rotation)
            offset_x, offset_y, width, height = resize_annotation_geometry(
                offset_x,
                offset_y,
                width,
                height,
                self._drag_mode,
                resize_delta.x(),
                resize_delta.y(),
            )
        self.record = replace(
            self.record,
            offset_x=offset_x,
            offset_y=offset_y,
            width=width,
            height=height,
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
        handle = self.resize_handle_at(event.pos())
        if self._edit_mode and not self.record.locked and handle is not None:
            self.setCursor(_cursor_for_handle(handle))
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



class TabletAnnotationOverlay(QWidget):
    """One professional annotation layer above the complete tablet canvas.

    The former implementation inserted every annotation into a track ViewBox.
    PyQtGraph then clipped the callout at the track edge and duplicated
    track-less annotations.  This transparent child spans the entire track
    canvas, so comments can move across columns while their depth/time/curve
    anchor remains stable.
    """

    edit_requested = Signal(str)
    delete_requested = Signal(str)
    duplicate_requested = Signal(str)
    context_requested = Signal(str, QPoint)
    geometry_changed = Signal(str, float, float, float, float)
    selection_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._entries: dict[str, tuple[TabletAnnotationItem, QPointF]] = {}
        self._order: list[str] = []
        self._edit_mode = False
        self._print_mode = False
        self._selected_id: str | None = None
        self._drag_mode: str | None = None
        self._drag_id: str | None = None
        self._press_position = QPointF()
        self._start_geometry = (0.0, 0.0, 40.0, 24.0)
        self._refresh_mouse_policy()

    @property
    def selected_annotation_id(self) -> str | None:
        return self._selected_id

    def set_entries(
        self,
        entries: list[tuple[AnnotationRecord, QPointF, QPixmap | None]],
    ) -> None:
        """Replace layer contents while reusing existing graphics helpers.

        Depth navigation can refresh annotation anchors many times per second.
        Reusing helpers avoids repeatedly rebuilding fonts, painter paths and
        image pixmaps while preserving selection and an active mouse gesture.
        """

        previous = self._selected_id
        old_entries = self._entries
        next_entries: dict[str, tuple[TabletAnnotationItem, QPointF]] = {}
        next_order: list[str] = []
        for record, anchor, pixmap in entries:
            annotation_id = record.annotation_id
            existing = old_entries.get(annotation_id)
            if existing is None:
                helper = TabletAnnotationItem(
                    record,
                    pixmap=pixmap,
                    edit_mode=self._edit_mode,
                    print_mode=self._print_mode,
                )
            else:
                helper, _old_anchor = existing
                # Do not overwrite the transient geometry while the user is
                # dragging. It is committed through geometry_changed on release.
                if annotation_id != self._drag_id:
                    helper.set_record(record, pixmap=pixmap)
                helper.set_edit_mode(self._edit_mode)
                helper.set_print_mode(self._print_mode)
            helper._selected = annotation_id == previous
            next_entries[annotation_id] = (helper, QPointF(anchor))
            next_order.append(annotation_id)

        self._entries = next_entries
        self._order = next_order
        if previous not in self._entries:
            self._selected_id = None
            if previous is not None:
                self.selection_changed.emit(None)
        self._update_mask()
        self.update()
        self.raise_()

    def set_anchor_positions(self, anchors: dict[str, QPointF]) -> None:
        """Synchronize screen anchors after depth/time navigation.

        Annotation geometry is stored as a pixel offset from a data-space
        anchor. Therefore every change of the visible depth/time range must
        remap that anchor into the current tablet canvas. This method updates
        positions only; it never changes text, style, size or saved offsets.
        """

        changed = False
        for annotation_id, (helper, current_anchor) in tuple(self._entries.items()):
            next_anchor = anchors.get(annotation_id)
            if next_anchor is None:
                continue
            normalized = QPointF(next_anchor)
            if current_anchor == normalized:
                continue
            self._entries[annotation_id] = (helper, normalized)
            changed = True
        if not changed:
            return
        self._update_mask()
        self.update()
        self.raise_()

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = bool(enabled)
        for helper, _anchor in self._entries.values():
            helper.set_edit_mode(self._edit_mode)
        if not self._edit_mode:
            self._drag_mode = None
            self._drag_id = None
            self.select_annotation(None)
        self._refresh_mouse_policy()
        self._update_mask()
        self.update()

    def set_print_mode(self, enabled: bool) -> None:
        self._print_mode = bool(enabled)
        for helper, _anchor in self._entries.values():
            helper.set_print_mode(self._print_mode)
        self._refresh_mouse_policy()
        self._update_mask()
        self.update()

    def select_annotation(self, annotation_id: str | None) -> None:
        normalized = annotation_id if annotation_id in self._entries else None
        if normalized == self._selected_id:
            return
        self._selected_id = normalized
        for current_id, (helper, _anchor) in self._entries.items():
            helper._selected = current_id == normalized
        self._update_mask()
        self.update()
        if normalized is not None:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.selection_changed.emit(normalized)

    def edit_selected(self) -> bool:
        if self._selected_id is None:
            return False
        self.edit_requested.emit(self._selected_id)
        return True

    def delete_selected(self) -> bool:
        if self._selected_id is None:
            return False
        self.delete_requested.emit(self._selected_id)
        return True

    def duplicate_selected(self) -> bool:
        if self._selected_id is None:
            return False
        self.duplicate_requested.emit(self._selected_id)
        return True

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            for annotation_id in self._order:
                helper, anchor = self._entries[annotation_id]
                if not helper.record.visible:
                    continue
                if self._print_mode and not helper.record.print_enabled:
                    continue
                painter.save()
                painter.translate(anchor)
                helper.paint(painter, QStyleOptionGraphicsItem(), self)
                painter.restore()
        finally:
            painter.end()

    def paint_translated(
        self,
        painter: QPainter,
        origin: QPointF,
        *,
        print_mode: bool = True,
    ) -> None:
        """Paint the global overlay into one track-local print surface."""

        painter.save()
        try:
            painter.translate(-origin.x(), -origin.y())
            for annotation_id in self._order:
                helper, anchor = self._entries[annotation_id]
                record = helper.record
                if not record.visible or (print_mode and not record.print_enabled):
                    continue
                was_selected = helper._selected
                helper._selected = False
                painter.save()
                painter.translate(anchor)
                helper.paint(painter, QStyleOptionGraphicsItem(), None)
                painter.restore()
                helper._selected = was_selected
        finally:
            painter.restore()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self._edit_mode or self._print_mode:
            event.ignore()
            return
        hit = self._hit(event.position())
        if event.button() == Qt.MouseButton.RightButton:
            if hit is not None:
                annotation_id, _helper, _local = hit
                self.select_annotation(annotation_id)
                self.context_requested.emit(annotation_id, event.globalPosition().toPoint())
                event.accept()
                return
            event.ignore()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        if hit is None:
            self.select_annotation(None)
            event.ignore()
            return
        annotation_id, helper, local = hit
        self.select_annotation(annotation_id)
        if helper.record.locked:
            event.accept()
            return
        handle = helper.resize_handle_at(local)
        box_local = helper._point_in_box_coordinates(local)
        if handle is None and not helper.box_rect().contains(box_local):
            event.accept()
            return
        self._drag_id = annotation_id
        self._drag_mode = handle or "move"
        self._press_position = QPointF(event.position())
        self._start_geometry = (
            helper.record.offset_x,
            helper.record.offset_y,
            helper.record.width,
            helper.record.height,
        )
        self.setCursor(_cursor_for_handle(handle) if handle else Qt.CursorShape.SizeAllCursor)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.grabMouse()
        self._update_mask()
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_id is None or self._drag_mode is None:
            self._update_hover_cursor(event.position())
            event.ignore()
            return
        helper, anchor = self._entries[self._drag_id]
        delta = QPointF(event.position()) - self._press_position
        offset_x, offset_y, width, height = self._start_geometry
        if self._drag_mode == "move":
            offset_x += delta.x()
            offset_y += delta.y()
        else:
            local_delta = _unrotate_delta(delta, helper.record.style.rotation)
            offset_x, offset_y, width, height = resize_annotation_geometry(
                offset_x,
                offset_y,
                width,
                height,
                self._drag_mode,
                local_delta.x(),
                local_delta.y(),
            )
        offset_x, offset_y = self._keep_reachable(
            anchor, offset_x, offset_y, width, height
        )
        helper.set_record(
            replace(
                helper.record,
                offset_x=offset_x,
                offset_y=offset_y,
                width=width,
                height=height,
            )
        )
        helper._selected = True
        self._entries[self._drag_id] = (helper, anchor)
        self._update_mask()
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag_id is None or self._drag_mode is None:
            event.ignore()
            return
        annotation_id = self._drag_id
        helper, _anchor = self._entries[annotation_id]
        self._drag_id = None
        self._drag_mode = None
        self.releaseMouse()
        self.unsetCursor()
        self._update_mask()
        self.geometry_changed.emit(
            annotation_id,
            helper.record.offset_x,
            helper.record.offset_y,
            helper.record.width,
            helper.record.height,
        )
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if not self._edit_mode or event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        hit = self._hit(event.position())
        if hit is None:
            event.ignore()
            return
        annotation_id, _helper, _local = hit
        self.select_annotation(annotation_id)
        self.edit_requested.emit(annotation_id)
        event.accept()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if not self._edit_mode or self._print_mode or self._selected_id is None:
            super().keyPressEvent(event)
            return
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_F2}:
            self.edit_requested.emit(self._selected_id)
            event.accept()
            return
        if event.key() in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace}:
            self.delete_requested.emit(self._selected_id)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.select_annotation(None)
            event.accept()
            return
        super().keyPressEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._drag_id is None:
            self.unsetCursor()
        super().leaveEvent(event)

    def _hit(
        self, point: QPointF
    ) -> tuple[str, TabletAnnotationItem, QPointF] | None:
        for annotation_id in reversed(self._order):
            helper, anchor = self._entries[annotation_id]
            if not helper.record.visible:
                continue
            local = QPointF(point) - anchor
            if helper.shape().contains(local):
                return annotation_id, helper, local
            if annotation_id == self._selected_id and helper.resize_handle_at(local) is not None:
                return annotation_id, helper, local
        return None

    def _update_hover_cursor(self, point: QPointF) -> None:
        if not self._edit_mode or self._print_mode:
            self.unsetCursor()
            return
        hit = self._hit(point)
        if hit is None:
            self.unsetCursor()
            return
        _annotation_id, helper, local = hit
        if helper.record.locked:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        handle = helper.resize_handle_at(local)
        self.setCursor(_cursor_for_handle(handle) if handle else Qt.CursorShape.SizeAllCursor)

    def _keep_reachable(
        self,
        anchor: QPointF,
        offset_x: float,
        offset_y: float,
        width: float,
        height: float,
    ) -> tuple[float, float]:
        return keep_annotation_reachable(
            anchor.x(),
            anchor.y(),
            offset_x,
            offset_y,
            width,
            height,
            self.width(),
            self.height(),
        )

    def _refresh_mouse_policy(self) -> None:
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            not self._edit_mode or self._print_mode,
        )

    def _update_mask(self) -> None:
        from PySide6.QtGui import QRegion

        # While dragging, keep the complete overlay active and explicitly grab
        # the mouse. This preserves movement even when the box crosses a track
        # boundary or the pointer temporarily leaves the old masked region.
        if self._drag_id is not None:
            self.setMask(QRegion(self.rect()))
            return

        region = QRegion()
        for annotation_id in self._order:
            helper, anchor = self._entries[annotation_id]
            if not helper.record.visible:
                continue
            transform = QTransform()
            transform.translate(anchor.x(), anchor.y())
            hit_path = transform.map(helper.shape())
            for polygon_f in hit_path.toSubpathPolygons():
                polygon = polygon_f.toPolygon()
                if not polygon.isEmpty():
                    region = region.united(QRegion(polygon))
            if annotation_id == self._selected_id:
                for handle_rect in helper.resize_handle_rects().values():
                    mapped = transform.mapRect(handle_rect).adjusted(-3.0, -3.0, 3.0, 3.0)
                    region = region.united(QRegion(mapped.toAlignedRect()))
        self.setMask(region)


def _unrotate_delta(delta: QPointF, rotation: float) -> QPointF:
    if not rotation:
        return QPointF(delta)
    angle = -float(rotation) * pi / 180.0
    return QPointF(
        delta.x() * cos(angle) - delta.y() * sin(angle),
        delta.x() * sin(angle) + delta.y() * cos(angle),
    )


def _cursor_for_handle(handle: str | None) -> Qt.CursorShape:
    if handle in {"nw", "se"}:
        return Qt.CursorShape.SizeFDiagCursor
    if handle in {"ne", "sw"}:
        return Qt.CursorShape.SizeBDiagCursor
    if handle in {"n", "s"}:
        return Qt.CursorShape.SizeVerCursor
    if handle in {"e", "w"}:
        return Qt.CursorShape.SizeHorCursor
    return Qt.CursorShape.SizeAllCursor

def _pen_style(value: str) -> Qt.PenStyle:
    return {
        "dash": Qt.PenStyle.DashLine,
        "dot": Qt.PenStyle.DotLine,
    }.get(value, Qt.PenStyle.SolidLine)
