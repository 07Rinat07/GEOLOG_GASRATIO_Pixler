from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, QTimer, Qt
from PySide6.QtGui import QAction, QMouseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.files.document_service import DocumentError, DocumentKind
from geoworkbench.ui.file_workspace_depth import FileWorkspaceWidget as _DepthWorkspace
from geoworkbench.ui.file_workspace_geometry import eraser_stroke_rectangles
from geoworkbench.ui.file_workspace_i18n import normalize_language
from geoworkbench.ui.file_workspace_v2 import _EraserOverlay


_OVERFLOW_TEXT: dict[str, str] = {
    "ru": "Текст не помещается: увеличьте область или уменьшите размер шрифта",
    "kk": "Мәтін сыймайды: аймақты үлкейтіңіз немесе қаріп өлшемін кішірейтіңіз",
    "en": "The text does not fit: enlarge the area or reduce the font size",
}


class _ContinuousEraserOverlay(_EraserOverlay):
    """Square eraser overlay that fills gaps between sparse mouse events."""

    def _append_interpolated(self, point: QPointF) -> None:
        if not self._points:
            self._points.append(point)
            return
        start = self._points[-1]
        distance = self._distance(start, point)
        if distance <= 0.5:
            return
        spacing = max(2.0, self._brush_size / 2.0)
        steps = max(1, math.ceil(distance / spacing))
        for index in range(1, steps + 1):
            ratio = index / steps
            self._points.append(
                QPointF(
                    start.x() + (point.x() - start.x()) * ratio,
                    start.y() + (point.y() - start.y()) * ratio,
                )
            )

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._active:
            super().mouseMoveEvent(event)
            return
        self._cursor = event.position().toPoint()
        if self._drawing:
            self._append_interpolated(event.position())
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._active and event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._append_interpolated(event.position())
            self._drawing = False
            points = list(self._points)
            self._points.clear()
            self.update()
            if points:
                self.stroke_completed.emit(points, self._brush_size)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class FileWorkspaceWidget(_DepthWorkspace):
    """Final hardening layer for PDF editing and live language switching."""

    def __init__(self, parent: QWidget | None = None, *, language: str = "ru") -> None:
        super().__init__(parent, language=language)
        self._language_sync_attempts = 0
        self._language_actions_connected = False
        self._replace_eraser_overlay()
        self._expand_calculator_panels()
        self._sync_document_state()
        QTimer.singleShot(0, self._install_language_sync)

    def _replace_eraser_overlay(self) -> None:
        old_overlay: Any = getattr(self, "_eraser_overlay", None)
        if old_overlay is not None:
            old_overlay.set_active(False)
            try:
                old_overlay.stroke_completed.disconnect()
            except RuntimeError:
                pass
            old_overlay.hide()
            old_overlay.setParent(None)
            old_overlay.deleteLater()

        overlay = _ContinuousEraserOverlay(self.document_canvas)
        overlay.setGeometry(self.document_canvas.rect())
        overlay.stroke_completed.connect(self._apply_eraser_stroke)
        self.eraser_size.valueChanged.connect(overlay.set_brush_size)
        overlay.set_brush_size(self.eraser_size.value())
        overlay.set_active(
            self.eraser_button.isChecked()
            and self.document_service.kind is DocumentKind.PDF
        )
        overlay.raise_()
        self._eraser_overlay = overlay

    def _expand_calculator_panels(self) -> None:
        engineering_page = self.sections.widget(4)
        page_layout = engineering_page.layout() if engineering_page is not None else None
        if isinstance(page_layout, QVBoxLayout) and engineering_page is not None:
            existing_scroll = engineering_page.findChild(
                QScrollArea, "engineeringCalculationsScroll"
            )
            if existing_scroll is None:
                content = QWidget(engineering_page)
                content.setObjectName("engineeringCalculationsContent")
                content_layout = QVBoxLayout(content)
                content_layout.setContentsMargins(8, 8, 8, 12)
                content_layout.setSpacing(max(10, page_layout.spacing()))
                while page_layout.count():
                    item = page_layout.takeAt(0)
                    widget = item.widget()
                    nested_layout = item.layout()
                    if widget is not None:
                        content_layout.addWidget(widget)
                    elif nested_layout is not None:
                        content_layout.addLayout(nested_layout)
                    else:
                        content_layout.addItem(item)

                scroll = QScrollArea(engineering_page)
                scroll.setObjectName("engineeringCalculationsScroll")
                scroll.setWidgetResizable(True)
                scroll.setFrameShape(QFrame.Shape.NoFrame)
                scroll.setHorizontalScrollBarPolicy(
                    Qt.ScrollBarPolicy.ScrollBarAsNeeded
                )
                scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                scroll.setWidget(content)
                page_layout.setContentsMargins(0, 0, 0, 0)
                page_layout.addWidget(scroll)

        tabs = self.findChild(QTabWidget, "petroleumCalculatorTabs")
        if tabs is None:
            return
        tabs.setMinimumHeight(520)
        tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
        )
        tabs.setUsesScrollButtons(True)

        group = tabs.parentWidget()
        if isinstance(group, QGroupBox):
            group.setMinimumHeight(600)
            group.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
            )
            group_layout = group.layout()
            if isinstance(group_layout, QVBoxLayout):
                group_layout.setStretchFactor(tabs, 1)

        for index in range(tabs.count()):
            calculator_page = tabs.widget(index)
            if calculator_page is None:
                continue
            calculator_page.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
            )
            calculator_layout = calculator_page.layout()
            if isinstance(calculator_layout, QFormLayout):
                calculator_layout.setFieldGrowthPolicy(
                    QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
                )
                calculator_layout.setRowWrapPolicy(
                    QFormLayout.RowWrapPolicy.WrapLongRows
                )
                calculator_layout.setLabelAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                calculator_layout.setHorizontalSpacing(18)
                calculator_layout.setVerticalSpacing(10)
            elif isinstance(calculator_layout, QGridLayout):
                calculator_layout.setColumnMinimumWidth(1, 300)
                calculator_layout.setColumnStretch(0, 0)
                calculator_layout.setColumnStretch(1, 0)
                calculator_layout.setColumnStretch(2, 1)
                calculator_layout.setColumnStretch(3, 1)
                calculator_layout.setHorizontalSpacing(14)
                calculator_layout.setVerticalSpacing(9)
                calculator_layout.setRowStretch(calculator_layout.rowCount(), 1)

            for label in calculator_page.findChildren(QLabel):
                label.setWordWrap(True)
                if label.objectName() == "hint":
                    label.setSizePolicy(
                        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
                    )
                    label.setAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                    )

        wide_controls = (
            "pipe_od_in",
            "pipe_wall_mm",
            "pipe_length_m",
            "pipe_density",
            "drill_mud_density",
            "drill_tvd",
            "drill_hole_d",
            "drill_pipe_d",
            "drill_interval",
            "drill_flow",
            "mud_density",
            "mud_annular_loss",
            "mud_tvd",
            "mix_v1",
            "mix_rho1",
            "mix_v2",
            "mix_rho2",
            "geo_reference",
            "geo_top_tvd",
            "geo_bottom_tvd",
            "depth_ground_elevation",
            "depth_reference_kind",
            "depth_datum_height",
            "depth_measured_depth",
            "depth_true_vertical_depth",
        )
        for name in wide_controls:
            control: Any = getattr(self, name, None)
            if isinstance(control, (QDoubleSpinBox, QSpinBox, QLineEdit, QComboBox)):
                control.setMinimumWidth(max(control.minimumWidth(), 300))
                control.setMinimumHeight(max(control.minimumHeight(), 36))
                control.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                )

        result_sizes = {
            "pipe_result": (180, 240),
            "drill_result": (220, 280),
            "mud_result": (220, 280),
            "geo_result": (160, 220),
            "depth_result": (260, 340),
        }
        for name, (minimum_height, maximum_height) in result_sizes.items():
            result: Any = getattr(self, name, None)
            if not isinstance(result, QLabel):
                continue
            result.setMinimumWidth(max(result.minimumWidth(), 620))
            result.setMinimumHeight(max(result.minimumHeight(), minimum_height))
            result.setMaximumHeight(maximum_height)
            result.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            result.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            result.setMargin(12)
            result.setWordWrap(True)
            result_layout = result.parentWidget().layout()
            if isinstance(result_layout, QFormLayout):
                self._make_form_result_full_width(result_layout, result)

    @staticmethod
    def _make_form_result_full_width(layout: QFormLayout, result: QLabel) -> None:
        row, role = layout.getWidgetPosition(result)
        if row < 0 or role == QFormLayout.ItemRole.SpanningRole:
            return
        title = layout.labelForField(result)
        layout.removeWidget(result)
        if title is not None:
            layout.removeWidget(title)
            if isinstance(title, QLabel):
                title.setStyleSheet("font-weight: 700;")
                title.setWordWrap(True)
            layout.addRow(title)
        layout.addRow(result)

    def _apply_eraser_stroke(self, points: list[QPointF], brush_size: int) -> None:
        rects = eraser_stroke_rectangles(points, brush_size, self._render_zoom)
        try:
            service = self._enhanced_service()
            service.erase_pdf_display_rects(rects)
            self._refresh_document()
            self.document_status.setText(self._t("eraser_done"))
        except DocumentError as error:
            self._show_error(self._t("tool_eraser"), error)

    def _sync_document_state(self) -> None:
        super()._sync_document_state()
        eraser_button: Any = getattr(self, "eraser_button", None)
        overlay: Any = getattr(self, "_eraser_overlay", None)
        is_pdf = self.document_service.kind is DocumentKind.PDF
        if not is_pdf:
            if eraser_button is not None and eraser_button.isChecked():
                eraser_button.blockSignals(True)
                eraser_button.setChecked(False)
                eraser_button.blockSignals(False)
            if overlay is not None:
                overlay.set_active(False)

    def _localized_error(self, error: Exception | str) -> str:
        message = str(error)
        if message == _OVERFLOW_TEXT["ru"]:
            return _OVERFLOW_TEXT.get(self.language, _OVERFLOW_TEXT["ru"])
        return super()._localized_error(error)

    def _install_language_sync(self) -> None:
        if self._language_actions_connected:
            return
        self._language_sync_attempts += 1
        window: Any = self.window()
        actions: Any = getattr(window, "language_actions", None)
        if isinstance(actions, dict) and actions:
            for action in actions.values():
                if isinstance(action, QAction):
                    action.triggered.connect(self._schedule_language_sync)
            self._language_actions_connected = True
            return
        if self._language_sync_attempts < 50:
            QTimer.singleShot(100, self._install_language_sync)

    def _schedule_language_sync(self, *_args: object) -> None:
        QTimer.singleShot(0, self._sync_language_from_window)

    def _sync_language_from_window(self) -> None:
        window: Any = self.window()
        language = getattr(window, "language", self.language)
        self.set_language(getattr(language, "value", language))

    def set_language(self, language: object) -> None:
        code = normalize_language(str(getattr(language, "value", language)))
        if code == self.language:
            return
        tabs = self._ancestor_tabs()
        if tabs is None:
            self.language = code
            self._localize_workspace()
            self._fix_help_cards()
            self._fix_document_panels()
            self._refresh_localized_document_labels()
            return

        index = tabs.indexOf(self)
        if index < 0:
            return
        host: Any = self.window()
        icon = tabs.tabIcon(index)
        tooltip = tabs.tabToolTip(index)
        was_current = tabs.currentWidget() is self
        section_index = self.sections.currentIndex()
        petroleum_tabs = self.findChild(QTabWidget, "petroleumCalculatorTabs")
        petroleum_index = petroleum_tabs.currentIndex() if petroleum_tabs is not None else 0
        render_zoom = self._render_zoom
        service = self.document_service

        self._deactivate_eraser()
        replacement = type(self)(tabs, language=code)
        replacement.document_service = service
        replacement._copy_control_state(self)
        replacement._render_zoom = render_zoom
        replacement.sections.setCurrentIndex(section_index)
        replacement_petroleum = replacement.findChild(QTabWidget, "petroleumCalculatorTabs")
        if replacement_petroleum is not None:
            replacement_petroleum.setCurrentIndex(
                max(0, min(petroleum_index, replacement_petroleum.count() - 1))
            )
        if service.is_open:
            replacement._refresh_document()
        else:
            replacement._sync_document_state()

        tabs.removeTab(index)
        tabs.insertTab(index, replacement, icon, replacement.tab_title(code))
        tabs.setTabToolTip(index, tooltip)
        if was_current:
            tabs.setCurrentIndex(index)
        if getattr(host, "file_workspace", None) is self:
            host.file_workspace = replacement
        self.setParent(None)
        self.deleteLater()

    def _deactivate_eraser(self) -> None:
        if self.eraser_button.isChecked():
            self.eraser_button.blockSignals(True)
            self.eraser_button.setChecked(False)
            self.eraser_button.blockSignals(False)
        self._eraser_overlay.set_active(False)

    def _ancestor_tabs(self) -> QTabWidget | None:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QTabWidget):
                return parent
            parent = parent.parentWidget()
        return None

    def _copy_control_state(self, source: FileWorkspaceWidget) -> None:
        for name, old_control in vars(source).items():
            if name in {"eraser_button", "_eraser_overlay"}:
                continue
            new_control: Any = getattr(self, name, None)
            if isinstance(old_control, QLineEdit) and isinstance(new_control, QLineEdit):
                new_control.setText(old_control.text())
            elif isinstance(old_control, QTextEdit) and isinstance(new_control, QTextEdit):
                new_control.setPlainText(old_control.toPlainText())
            elif isinstance(old_control, QDoubleSpinBox) and isinstance(
                new_control, QDoubleSpinBox
            ):
                new_control.setValue(old_control.value())
            elif isinstance(old_control, QSpinBox) and isinstance(new_control, QSpinBox):
                new_control.setValue(old_control.value())
            elif isinstance(old_control, QComboBox) and isinstance(new_control, QComboBox):
                new_control.setCurrentIndex(
                    max(0, min(old_control.currentIndex(), new_control.count() - 1))
                )
            elif isinstance(old_control, QCheckBox) and isinstance(new_control, QCheckBox):
                new_control.setChecked(old_control.isChecked())

        archive_sources: Any = getattr(source, "_archive_sources", None)
        if isinstance(archive_sources, list):
            self._archive_sources = list(archive_sources)
