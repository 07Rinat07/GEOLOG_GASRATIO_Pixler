from __future__ import annotations

from dataclasses import dataclass, replace
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
    QLabel,
    QStyleOptionGraphicsItem,
    QWidget,
)

from geoworkbench.project.annotation_schema import AnnotationKind, AnnotationRecord
from geoworkbench.tablet.annotation_layout import (
    LayoutPoint,
    LayoutRect,
    annotation_box_rect,
    annotation_leader_endpoint,
)
from geoworkbench.tablet.annotation_interaction import (
    keep_annotation_reachable,
    resize_annotation_geometry,
)
from geoworkbench.tablet.annotation_tool import (
    AnnotationGeometryChange,
    AnnotationSurfaceHit,
)


class TabletAnnotationItem(QGraphicsObject):
    """Device-sized annotation anchored to a plot data point.

    The anchor follows depth/time/curve coordinates in the ViewBox while the
    callout box keeps a predictable physical screen size. The same QGraphicsItem
    is rendered by QWidget/PDF/print capture, preventing screen/print drift.
    """

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
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        # The current overlay paints this helper into mouse-transparent sprites,
        # while print/export and compatibility integrations may still put it in
        # a QGraphicsScene and route events through the item itself.
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptedMouseButtons(
            Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton
        )
        self.setAcceptHoverEvents(False)
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
        geometry = annotation_box_rect(self.record)
        return QRectF(geometry.left, geometry.top, geometry.width, geometry.height)

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
        endpoint = annotation_leader_endpoint(
            LayoutPoint(0.0, 0.0),
            box=LayoutRect(rect.left(), rect.top(), rect.width(), rect.height()),
            rotation_degrees=float(self.record.style.rotation),
        )
        return QPointF(endpoint.x, endpoint.y)




@dataclass(slots=True)
class _AnnotationGesture:
    annotation_id: str
    mode: str
    press_position: QPointF
    start_geometry: tuple[float, float, float, float]


class TabletAnnotationOverlay(QWidget):
    """Annotation interaction model with per-object paint sprites.

    A single translucent widget covering PyQtGraph viewports is not safe on
    Windows: depending on the graphics backend it can be composed as an opaque
    black rectangle.  This class therefore never paints a full-canvas surface.
    It remains a hidden QObject/QWidget manager for signals and geometry, while
    every visible annotation is rendered into its own small alpha QPixmap shown
    by a mouse-transparent QLabel parented directly to the tablet canvas.

    The sprite rectangles are clipped to the graph body.  Consequently no
    native child window exists over empty graph space, track headers remain
    unobscured, and annotations still share one global coordinate system.
    """

    edit_requested = Signal(str)
    delete_requested = Signal(str)
    duplicate_requested = Signal(str)
    context_requested = Signal(str, QPoint)
    geometry_changed = Signal(str, float, float, float, float)
    selection_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._canvas = parent
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # The manager itself must never become a visible full-size child.  Only
        # the small QLabel sprites created below are shown.
        self.hide()

        self._entries: dict[str, tuple[TabletAnnotationItem, QPointF]] = {}
        self._order: list[str] = []
        self._sprites: dict[str, QLabel] = {}
        self._edit_mode = False
        self._print_mode = False
        self._selected_id: str | None = None
        self._gesture: _AnnotationGesture | None = None
        self._content_rect = QRectF()

    @property
    def interaction_active(self) -> bool:
        return self._gesture is not None

    @property
    def selected_annotation_id(self) -> str | None:
        return self._selected_id

    @property
    def annotation_ids(self) -> tuple[str, ...]:
        return tuple(self._order)

    def annotation_item(self, annotation_id: str) -> TabletAnnotationItem | None:
        entry = self._entries.get(annotation_id)
        return entry[0] if entry is not None else None

    @property
    def content_rect(self) -> QRectF:
        return QRectF(self._content_rect)

    def set_content_rect(self, rect: QRectF) -> None:
        canvas_rect = QRectF(self._canvas.rect()) if self._canvas is not None else QRectF(rect)
        normalized = QRectF(rect).normalized().intersected(canvas_rect)
        if normalized == self._content_rect:
            return
        self._content_rect = normalized
        self._refresh_sprites()

    def set_entries(
        self,
        entries: list[tuple[AnnotationRecord, QPointF, QPixmap | None]],
    ) -> None:
        previous = self._selected_id
        old_entries = self._entries
        next_entries: dict[str, tuple[TabletAnnotationItem, QPointF]] = {}
        next_order: list[str] = []
        active_id = self._gesture.annotation_id if self._gesture is not None else None
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
                if annotation_id != active_id:
                    helper.set_record(record, pixmap=pixmap)
                helper.set_edit_mode(self._edit_mode)
                helper.set_print_mode(self._print_mode)
            helper._selected = annotation_id == previous
            next_entries[annotation_id] = (helper, QPointF(anchor))
            next_order.append(annotation_id)

        if active_id is not None and active_id not in next_entries:
            self.cancel_interaction()

        removed = set(self._entries) - set(next_entries)
        self._entries = next_entries
        self._order = next_order
        for annotation_id in removed:
            self._delete_sprite(annotation_id)

        if previous not in self._entries:
            self._selected_id = None
            if previous is not None:
                self.selection_changed.emit(None)
        self._refresh_sprites()

    def set_anchor_positions(self, anchors: dict[str, QPointF]) -> None:
        changed_ids: list[str] = []
        for annotation_id, (helper, current_anchor) in tuple(self._entries.items()):
            next_anchor = anchors.get(annotation_id)
            if next_anchor is None:
                continue
            normalized = QPointF(next_anchor)
            if current_anchor == normalized:
                continue
            self._entries[annotation_id] = (helper, normalized)
            changed_ids.append(annotation_id)
        for annotation_id in changed_ids:
            self._refresh_sprite(annotation_id)
        self._raise_sprites()

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = bool(enabled)
        for helper, _anchor in self._entries.values():
            helper.set_edit_mode(self._edit_mode)
        if not self._edit_mode:
            self.cancel_interaction()
            self.select_annotation(None)
        self._refresh_sprites()

    def set_print_mode(self, enabled: bool) -> None:
        self._print_mode = bool(enabled)
        for helper, _anchor in self._entries.values():
            helper.set_print_mode(self._print_mode)
        if self._print_mode:
            self.cancel_interaction()
        self._refresh_sprites()

    def select_annotation(self, annotation_id: str | None) -> None:
        normalized = annotation_id if annotation_id in self._entries else None
        if normalized == self._selected_id:
            return
        previous = self._selected_id
        self._selected_id = normalized
        for current_id, (helper, _anchor) in self._entries.items():
            helper._selected = current_id == normalized
        if previous is not None:
            self._refresh_sprite(previous)
        if normalized is not None:
            self._refresh_sprite(normalized)
        self._raise_sprites()
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

    def hit_test(self, x: float, y: float) -> AnnotationSurfaceHit | None:
        hit = self._hit(QPointF(float(x), float(y)))
        if hit is None:
            return None
        annotation_id, helper, local = hit
        handle = helper.resize_handle_at(local)
        box_local = helper._point_in_box_coordinates(local)
        movable = handle is not None or helper.box_rect().contains(box_local)
        return AnnotationSurfaceHit(
            annotation_id=annotation_id,
            locked=bool(helper.record.locked),
            resize_handle=handle,
            movable=movable,
        )

    def hover_cursor(self, x: float, y: float) -> str | None:
        hit = self.hit_test(x, y)
        if hit is None:
            return None
        if hit.locked or not hit.movable:
            return "arrow"
        return _cursor_name_for_handle(hit.resize_handle)

    def begin_interaction(
        self,
        hit: AnnotationSurfaceHit,
        x: float,
        y: float,
    ) -> bool:
        if not self._edit_mode or self._print_mode or hit.locked or not hit.movable:
            return False
        entry = self._entries.get(hit.annotation_id)
        if entry is None:
            return False
        helper, _anchor = entry
        self.select_annotation(hit.annotation_id)
        self._gesture = _AnnotationGesture(
            annotation_id=hit.annotation_id,
            mode=hit.resize_handle or "move",
            press_position=QPointF(float(x), float(y)),
            start_geometry=(
                helper.record.offset_x,
                helper.record.offset_y,
                helper.record.width,
                helper.record.height,
            ),
        )
        return True

    def update_interaction(self, x: float, y: float) -> None:
        gesture = self._gesture
        if gesture is None:
            return
        entry = self._entries.get(gesture.annotation_id)
        if entry is None:
            self.cancel_interaction()
            return
        helper, anchor = entry
        delta = QPointF(float(x), float(y)) - gesture.press_position
        offset_x, offset_y, width, height = gesture.start_geometry
        if gesture.mode == "move":
            offset_x += delta.x()
            offset_y += delta.y()
        else:
            local_delta = _unrotate_delta(delta, helper.record.style.rotation)
            offset_x, offset_y, width, height = resize_annotation_geometry(
                offset_x,
                offset_y,
                width,
                height,
                gesture.mode,
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
        self._entries[gesture.annotation_id] = (helper, anchor)
        self._refresh_sprite(gesture.annotation_id)
        self._raise_sprites()

    def finish_interaction(
        self,
        *,
        commit: bool,
    ) -> AnnotationGeometryChange | None:
        gesture = self._gesture
        if gesture is None:
            return None
        self._gesture = None
        entry = self._entries.get(gesture.annotation_id)
        if entry is None:
            return None
        helper, anchor = entry
        current = (
            helper.record.offset_x,
            helper.record.offset_y,
            helper.record.width,
            helper.record.height,
        )
        if not commit:
            helper.set_record(
                replace(
                    helper.record,
                    offset_x=gesture.start_geometry[0],
                    offset_y=gesture.start_geometry[1],
                    width=gesture.start_geometry[2],
                    height=gesture.start_geometry[3],
                )
            )
            self._entries[gesture.annotation_id] = (helper, anchor)
            self._refresh_sprite(gesture.annotation_id)
            return None
        self._refresh_sprite(gesture.annotation_id)
        if not _geometry_differs(gesture.start_geometry, current):
            return None
        change = AnnotationGeometryChange(gesture.annotation_id, *current)
        self.geometry_changed.emit(
            change.annotation_id,
            change.offset_x,
            change.offset_y,
            change.width,
            change.height,
        )
        return change

    def cancel_interaction(self) -> None:
        self.finish_interaction(commit=False)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._canvas is not None:
            self._content_rect = self._content_rect.intersected(QRectF(self._canvas.rect()))
        self._refresh_sprites()

    def paintEvent(self, event) -> None:  # noqa: N802
        # Deliberately empty: a full-size overlay is the source of the Windows
        # black-canvas regression.  Annotation sprites paint independently.
        del event

    def paint_translated(
        self,
        painter: QPainter,
        origin: QPointF,
        *,
        print_mode: bool = True,
    ) -> None:
        painter.save()
        try:
            painter.translate(-origin.x(), -origin.y())
            if self._content_rect.isEmpty():
                return
            painter.setClipRect(self._content_rect, Qt.ClipOperation.IntersectClip)
            for annotation_id in self._order:
                helper, anchor = self._entries[annotation_id]
                record = helper.record
                if (
                    not record.visible
                    or not self._anchor_is_visible(anchor)
                    or (print_mode and not record.print_enabled)
                ):
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

    def _ensure_sprite(self, annotation_id: str) -> QLabel | None:
        if self._canvas is None:
            return None
        sprite = self._sprites.get(annotation_id)
        if sprite is not None:
            return sprite
        sprite = QLabel(self._canvas)
        sprite.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        sprite.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        sprite.setAutoFillBackground(False)
        sprite.setScaledContents(False)
        sprite.setStyleSheet("background: transparent; border: none; padding: 0px;")
        sprite.hide()
        self._sprites[annotation_id] = sprite
        return sprite

    def _delete_sprite(self, annotation_id: str) -> None:
        sprite = self._sprites.pop(annotation_id, None)
        if sprite is not None:
            sprite.hide()
            sprite.deleteLater()

    def _refresh_sprites(self) -> None:
        for annotation_id in tuple(self._sprites):
            if annotation_id not in self._entries:
                self._delete_sprite(annotation_id)
        for annotation_id in self._order:
            self._refresh_sprite(annotation_id)
        self._raise_sprites()

    def _refresh_sprite(self, annotation_id: str) -> None:
        entry = self._entries.get(annotation_id)
        sprite = self._ensure_sprite(annotation_id)
        if entry is None or sprite is None:
            return
        helper, anchor = entry
        record = helper.record
        if (
            self._content_rect.isEmpty()
            or not record.visible
            or not self._anchor_is_visible(anchor)
            or (self._print_mode and not record.print_enabled)
        ):
            sprite.hide()
            sprite.clear()
            return

        full_bounds = helper.boundingRect().translated(anchor).adjusted(-2.0, -2.0, 2.0, 2.0)
        visible_bounds = full_bounds.intersected(self._content_rect)
        target = visible_bounds.toAlignedRect()
        if target.isEmpty():
            sprite.hide()
            sprite.clear()
            return

        dpr = max(
            1.0,
            float(self._canvas.devicePixelRatioF()) if self._canvas is not None else 1.0,
        )
        pixel_width = max(1, int(round(target.width() * dpr)))
        pixel_height = max(1, int(round(target.height() * dpr)))
        pixmap = QPixmap(pixel_width, pixel_height)
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.translate(anchor.x() - target.left(), anchor.y() - target.top())
            helper.paint(painter, QStyleOptionGraphicsItem(), None)
        finally:
            painter.end()

        sprite.setGeometry(target)
        sprite.setPixmap(pixmap)
        sprite.show()

    def _raise_sprites(self) -> None:
        # Preserve document z-order.  Later records are painted above earlier
        # ones, while all sprites remain below unrelated top-level UI windows.
        for annotation_id in self._order:
            sprite = self._sprites.get(annotation_id)
            if sprite is not None and sprite.isVisible():
                sprite.raise_()

    def _hit(
        self, point: QPointF
    ) -> tuple[str, TabletAnnotationItem, QPointF] | None:
        if self._content_rect.isEmpty() or not self._content_rect.contains(point):
            return None
        for annotation_id in reversed(self._order):
            helper, anchor = self._entries[annotation_id]
            if not helper.record.visible or not self._anchor_is_visible(anchor):
                continue
            local = QPointF(point) - anchor
            if annotation_id == self._selected_id and helper.resize_handle_at(local) is not None:
                return annotation_id, helper, local
            if helper.shape().contains(local):
                return annotation_id, helper, local
        return None

    def _keep_reachable(
        self,
        anchor: QPointF,
        offset_x: float,
        offset_y: float,
        width: float,
        height: float,
    ) -> tuple[float, float]:
        rect = self._content_rect
        if rect.isEmpty():
            return offset_x, offset_y
        local_anchor = anchor - rect.topLeft()
        return keep_annotation_reachable(
            local_anchor.x(),
            local_anchor.y(),
            offset_x,
            offset_y,
            width,
            height,
            rect.width(),
            rect.height(),
        )

    def _anchor_is_visible(self, anchor: QPointF) -> bool:
        if self._content_rect.isEmpty():
            return False
        tolerance = 1.0
        return (
            self._content_rect.top() - tolerance
            <= anchor.y()
            <= self._content_rect.bottom() + tolerance
        )


def _geometry_differs(
    start: tuple[float, float, float, float],
    current: tuple[float, float, float, float],
    *,
    tolerance: float = 0.01,
) -> bool:
    """Return True only for a meaningful drag/resize geometry change."""

    return any(
        abs(float(before) - float(after)) > tolerance
        for before, after in zip(start, current)
    )


def _unrotate_delta(delta: QPointF, rotation: float) -> QPointF:
    if not rotation:
        return QPointF(delta)
    angle = -float(rotation) * pi / 180.0
    return QPointF(
        delta.x() * cos(angle) - delta.y() * sin(angle),
        delta.x() * sin(angle) + delta.y() * cos(angle),
    )



def _cursor_name_for_handle(handle: str | None) -> str:
    if handle in {"nw", "se"}:
        return "size_fdiag"
    if handle in {"ne", "sw"}:
        return "size_bdiag"
    if handle in {"n", "s"}:
        return "size_ver"
    if handle in {"e", "w"}:
        return "size_hor"
    return "size_all"

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
