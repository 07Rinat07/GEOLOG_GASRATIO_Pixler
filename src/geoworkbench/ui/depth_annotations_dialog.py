from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict, cast

import numpy as np

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import IndexRole, IndexType
from geoworkbench.printing.image_assets import ImageAssetError
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.annotation_schema import (
    AnnotationAnchor,
    AnnotationKind,
    AnnotationRecord,
    AnnotationStyle,
    STYLE_PRESETS,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.time_display import format_elapsed_time, format_unix_seconds


class _AnnotationValues(TypedDict):
    kind: AnnotationKind
    anchor: AnnotationAnchor
    text: str
    track_id: str | None
    depth: float
    axis_value: float | None
    axis_id: str | None
    parameter_mnemonic: str | None
    parameter_value: float | None
    unit: str
    x_fraction: float
    offset_x: float
    offset_y: float
    width: float
    height: float
    style: AnnotationStyle
    asset_ref: str | None
    visible: bool
    locked: bool
    print_enabled: bool


class _ColorButton(QPushButton):
    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        candidate = QColor(color)
        self._color = candidate.name() if candidate.isValid() else "#ffffff"
        self.clicked.connect(self._choose)
        self._refresh()

    @property
    def color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        candidate = QColor(color)
        if candidate.isValid():
            self._color = candidate.name()
            self._refresh()

    def _choose(self) -> None:
        selected = QColorDialog.getColor(QColor(self._color), self)
        if selected.isValid():
            self._color = selected.name()
            self._refresh()

    def _refresh(self) -> None:
        foreground = "#ffffff" if QColor(self._color).lightness() < 128 else "#111827"
        self.setText(self._color.upper())
        self.setStyleSheet(
            f"QPushButton {{ background:{self._color}; color:{foreground}; "
            "border:1px solid #64748b; border-radius:4px; padding:4px 8px; }}"
        )


class DepthAnnotationsDialog(QDialog):
    """Unified manager and style editor for tablet annotations."""

    annotations_changed = Signal()

    def __init__(
        self,
        controller: DepthAnnotationController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        initial_values: dict[str, object] | None = None,
        annotation_id: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.controller = controller
        self.controller.adopt_unscoped_annotations()
        self._single_item_mode = initial_values is not None or annotation_id is not None
        self._editing_annotation_id = annotation_id
        self.result_annotation_id: str | None = None
        self._asset_ref: str | None = None
        self._initial_values = dict(initial_values or {})
        self._axis_id: str | None = (
            str(self._initial_values["axis_id"])
            if self._initial_values.get("axis_id")
            else None
        )
        self._parameter_value: float | None = (
            self._initial_float(self._initial_values["parameter_value"])
            if self._initial_values.get("parameter_value") is not None
            else None
        )
        self._unit = str(self._initial_values.get("unit", ""))
        window_key = (
            "annotations.edit_window_title"
            if annotation_id is not None
            else "annotations.create_window_title"
            if initial_values is not None
            else "annotations.window_title"
        )
        self.setWindowTitle(self._t(window_key))
        self.resize(760 if self._single_item_mode else 1180, 720)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        hint = QLabel(self._t("annotations.editor_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "background:#eff6ff; border:1px solid #93c5fd; border-radius:6px; "
            "padding:7px 10px; color:#1e3a8a;"
        )
        root.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        table_panel = self._build_table_panel()
        splitter.addWidget(table_panel)
        splitter.addWidget(self._build_editor_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 5)
        if self._single_item_mode:
            table_panel.hide()
            splitter.setSizes([0, 760])
        root.addWidget(splitter, 1)

        if not self._single_item_mode:
            root.addLayout(self._build_actions())
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.button(QDialogButtonBox.StandardButton.Close).setText(
                self._t("common.close")
            )
            buttons.rejected.connect(self.reject)
        else:
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save
                | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.button(QDialogButtonBox.StandardButton.Save).setText(
                self._t("annotations.save_action")
            )
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
                self._t("common.cancel")
            )
            buttons.accepted.connect(self._save_single_item)
            buttons.rejected.connect(self.reject)
            if annotation_id is not None:
                delete_button = buttons.addButton(
                    self._t("annotations.delete_action"),
                    QDialogButtonBox.ButtonRole.DestructiveRole,
                )
                delete_button.setObjectName("annotation-delete-single-button")
                delete_button.clicked.connect(self._delete_single_item)
        root.addWidget(buttons)

        self._refresh_tracks_and_curves()
        self._refresh()
        self._apply_initial_values()
        if annotation_id is not None:
            self._select_annotation(annotation_id)
        elif self._single_item_mode:
            self.text_input.setFocus(Qt.FocusReason.OtherFocusReason)

    @staticmethod
    def _numeric_index_values(index) -> np.ndarray:
        """Return a stable numeric representation for depth/time spin boxes.

        This method belongs to the dialog.  In 0.7.15/0.7.16 it was
        accidentally nested in ``_ColorButton``; creating the dialog therefore
        raised ``AttributeError`` from toolbar actions and looked like an
        unresponsive F4 button to the user.
        """

        raw = np.asarray(index.values)
        if index.index_type is IndexType.DATETIME:
            dates = raw.astype("datetime64[ns]")
            numeric = dates.astype(np.int64).astype(np.float64) / 1_000_000_000.0
            numeric[np.isnat(dates)] = np.nan
            return numeric
        try:
            return raw.astype(np.float64)
        except (TypeError, ValueError):
            return np.full(raw.shape, np.nan, dtype=np.float64)

    def _axis_selection_changed(self, _index: int | None = None) -> None:
        dataset = self.controller.session.current_dataset
        axis_id = self.axis_id_input.currentData()
        self._axis_id = str(axis_id) if axis_id else None
        if dataset is None or self._axis_id not in dataset.indexes:
            return
        index = dataset.indexes[self._axis_id]
        numeric_axis = self._numeric_index_values(index)
        finite_axis = numeric_axis[np.isfinite(numeric_axis)]
        if not finite_axis.size:
            return
        minimum = float(np.min(finite_axis))
        maximum = float(np.max(finite_axis))
        if minimum == maximum:
            maximum = minimum + 1.0
        self.axis_input.setRange(minimum, maximum)
        if not self._initial_values:
            self.axis_input.setValue((minimum + maximum) / 2.0)
        self._refresh_axis_display()

    def _refresh_axis_display(self, _value: float | None = None) -> None:
        dataset = self.controller.session.current_dataset
        axis_id = self.axis_id_input.currentData()
        if dataset is None or not axis_id or str(axis_id) not in dataset.indexes:
            self.axis_display.setText("—")
            return
        index = dataset.indexes[str(axis_id)]
        value = float(self.axis_input.value())
        if index.index_type is IndexType.DATETIME:
            self.axis_display.setText(format_unix_seconds(value, timezone_name=index.timezone))
        elif index.role is IndexRole.TIME:
            self.axis_display.setText(format_elapsed_time(value, index.unit))
        else:
            suffix = f" {index.unit}" if index.unit else ""
            self.axis_display.setText(f"{value:g}{suffix}")

    def _build_table_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel(self._t("annotations.layer_title"))
        title.setStyleSheet("font-weight:700; font-size:14px;")
        layout.addWidget(title)
        self.table = QTableWidget(0, 6)
        self.table.setObjectName("depth-annotations-table")
        self.table.setHorizontalHeaderLabels(
            [
                self._t("annotations.depth"),
                self._t("annotations.comment"),
                self._t("annotations.kind"),
                self._t("annotations.track"),
                self._t("annotations.anchor"),
                self._t("annotations.print"),
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._load_selected)
        self.table.itemDoubleClicked.connect(lambda _item: self._load_selected())
        layout.addWidget(self.table, 1)
        return panel

    def _build_editor_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        tabs.addTab(self._build_content_tab(), self._t("annotations.content_tab"))
        tabs.addTab(self._build_style_tab(), self._t("annotations.style_tab"))
        tabs.addTab(self._build_geometry_tab(), self._t("annotations.geometry_tab"))
        layout.addWidget(tabs)
        return panel

    def _build_content_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.kind_input = QComboBox()
        for kind, key in (
            (AnnotationKind.CALLOUT, "annotations.kind_callout"),
            (AnnotationKind.COMMENT, "annotations.kind_comment"),
            (AnnotationKind.VALUE, "annotations.kind_value"),
            (AnnotationKind.IMAGE, "annotations.kind_image"),
            (AnnotationKind.SYMBOL, "annotations.kind_symbol"),
        ):
            self.kind_input.addItem(self._t(key), kind.value)
        self.kind_input.currentIndexChanged.connect(self._update_field_visibility)
        form.addRow(self._t("annotations.kind"), self.kind_input)

        self.anchor_input = QComboBox()
        for anchor, key in (
            (AnnotationAnchor.DEPTH, "annotations.anchor_depth"),
            (AnnotationAnchor.TIME, "annotations.anchor_time"),
            (AnnotationAnchor.CURVE, "annotations.anchor_curve"),
            (AnnotationAnchor.TRACK, "annotations.anchor_track"),
        ):
            self.anchor_input.addItem(self._t(key), anchor.value)
        self.anchor_input.currentIndexChanged.connect(self._update_field_visibility)
        form.addRow(self._t("annotations.anchor"), self.anchor_input)

        self.track_input = QComboBox()
        form.addRow(self._t("annotations.track"), self.track_input)
        self.parameter_input = QComboBox()
        form.addRow(self._t("annotations.parameter"), self.parameter_input)

        self.axis_id_input = QComboBox()
        self.axis_id_input.currentIndexChanged.connect(self._axis_selection_changed)
        form.addRow(self._t("annotations.axis"), self.axis_id_input)

        self.depth_input = QDoubleSpinBox()
        self.depth_input.setRange(-100_000.0, 100_000.0)
        self.depth_input.setDecimals(3)
        form.addRow(self._t("annotations.depth"), self.depth_input)

        self.axis_input = QDoubleSpinBox()
        self.axis_input.setRange(-1.0e15, 1.0e15)
        self.axis_input.setDecimals(6)
        self.axis_input.valueChanged.connect(self._refresh_axis_display)
        form.addRow(self._t("annotations.axis_value"), self.axis_input)
        self.axis_display = QLabel("—")
        self.axis_display.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.axis_display.setStyleSheet("font-weight:600; color:#0f766e;")
        form.addRow(self._t("annotations.axis_display"), self.axis_display)

        self.text_input = QTextEdit()
        self.text_input.setAcceptRichText(False)
        self.text_input.setMinimumHeight(120)
        self.text_input.setPlaceholderText(self._t("annotations.text_placeholder"))
        form.addRow(self._t("annotations.comment"), self.text_input)

        image_row = QWidget()
        image_layout = QHBoxLayout(image_row)
        image_layout.setContentsMargins(0, 0, 0, 0)
        self.asset_name = QLineEdit()
        self.asset_name.setReadOnly(True)
        self.asset_name.setPlaceholderText(self._t("annotations.no_image"))
        image_button = QPushButton(self._t("annotations.choose_image"))
        image_button.clicked.connect(self._choose_image)
        clear_image = QPushButton(self._t("common.clear"))
        clear_image.clicked.connect(self._clear_image)
        image_layout.addWidget(self.asset_name, 1)
        image_layout.addWidget(image_button)
        image_layout.addWidget(clear_image)
        form.addRow(self._t("annotations.image"), image_row)

        state_row = QWidget()
        state_layout = QHBoxLayout(state_row)
        state_layout.setContentsMargins(0, 0, 0, 0)
        self.visible_input = QCheckBox(self._t("annotations.visible"))
        self.visible_input.setChecked(True)
        self.locked_input = QCheckBox(self._t("annotations.locked"))
        self.print_input = QCheckBox(self._t("annotations.print_enabled"))
        self.print_input.setChecked(True)
        state_layout.addWidget(self.visible_input)
        state_layout.addWidget(self.locked_input)
        state_layout.addWidget(self.print_input)
        state_layout.addStretch(1)
        form.addRow(self._t("annotations.state"), state_row)
        return page

    def _build_style_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.preset_input = QComboBox()
        for preset_id, key in (
            ("professional", "annotations.preset_professional"),
            ("information", "annotations.preset_information"),
            ("warning", "annotations.preset_warning"),
            ("critical", "annotations.preset_critical"),
            ("neutral", "annotations.preset_neutral"),
        ):
            self.preset_input.addItem(self._t(key), preset_id)
        apply_preset = QPushButton(self._t("annotations.apply_preset"))
        apply_preset.clicked.connect(self._apply_style_preset)
        preset_row = QWidget()
        preset_layout = QHBoxLayout(preset_row)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.addWidget(self.preset_input, 1)
        preset_layout.addWidget(apply_preset)
        form.addRow(self._t("annotations.preset"), preset_row)

        self.font_input = QFontComboBox()
        form.addRow(self._t("annotations.font"), self.font_input)
        self.font_size_input = self._number_input(4.0, 96.0, 10.0, decimals=1)
        form.addRow(self._t("annotations.font_size"), self.font_size_input)

        font_flags = QWidget()
        flags_layout = QHBoxLayout(font_flags)
        flags_layout.setContentsMargins(0, 0, 0, 0)
        self.bold_input = QCheckBox(self._t("annotations.bold"))
        self.italic_input = QCheckBox(self._t("annotations.italic"))
        self.underline_input = QCheckBox(self._t("annotations.underline"))
        flags_layout.addWidget(self.bold_input)
        flags_layout.addWidget(self.italic_input)
        flags_layout.addWidget(self.underline_input)
        flags_layout.addStretch(1)
        form.addRow(self._t("annotations.font_style"), font_flags)

        self.text_color_input = _ColorButton("#0f172a")
        self.fill_color_input = _ColorButton("#ffffff")
        self.border_color_input = _ColorButton("#2563eb")
        self.leader_color_input = _ColorButton("#2563eb")
        form.addRow(self._t("annotations.text_color"), self.text_color_input)
        form.addRow(self._t("annotations.fill_color"), self.fill_color_input)
        form.addRow(self._t("annotations.border_color"), self.border_color_input)
        form.addRow(self._t("annotations.leader_color"), self.leader_color_input)

        self.fill_opacity_input = self._number_input(0.0, 1.0, 0.94, decimals=2)
        self.border_width_input = self._number_input(0.0, 20.0, 1.2, decimals=1)
        self.leader_width_input = self._number_input(0.0, 20.0, 1.2, decimals=1)
        form.addRow(self._t("annotations.opacity"), self.fill_opacity_input)
        form.addRow(self._t("annotations.border_width"), self.border_width_input)
        form.addRow(self._t("annotations.leader_width"), self.leader_width_input)

        self.border_style_input = self._style_combo()
        self.leader_style_input = self._style_combo()
        self.arrow_input = QComboBox()
        for value, key in (
            ("triangle", "annotations.arrow_triangle"),
            ("open", "annotations.arrow_open"),
            ("circle", "annotations.arrow_circle"),
            ("none", "annotations.arrow_none"),
        ):
            self.arrow_input.addItem(self._t(key), value)
        form.addRow(self._t("annotations.border_style"), self.border_style_input)
        form.addRow(self._t("annotations.leader_style"), self.leader_style_input)
        form.addRow(self._t("annotations.arrow_style"), self.arrow_input)

        self.alignment_input = QComboBox()
        for value, key in (
            ("left", "annotations.align_left"),
            ("center", "annotations.align_center"),
            ("right", "annotations.align_right"),
        ):
            self.alignment_input.addItem(self._t(key), value)
        form.addRow(self._t("annotations.alignment"), self.alignment_input)

        self.vertical_alignment_input = QComboBox()
        for value, key in (
            ("top", "annotations.align_top"),
            ("center", "annotations.align_middle"),
            ("bottom", "annotations.align_bottom"),
        ):
            self.vertical_alignment_input.addItem(self._t(key), value)
        form.addRow(self._t("annotations.vertical_alignment"), self.vertical_alignment_input)

        self.shadow_input = QCheckBox(self._t("annotations.shadow"))
        self.shadow_input.setChecked(True)
        form.addRow("", self.shadow_input)
        self.shadow_blur_input = self._number_input(0.0, 32.0, 5.0, decimals=1, suffix=" px")
        self.shadow_offset_x_input = self._number_input(-64.0, 64.0, 2.0, decimals=1, suffix=" px")
        self.shadow_offset_y_input = self._number_input(-64.0, 64.0, 2.0, decimals=1, suffix=" px")
        form.addRow(self._t("annotations.shadow_blur"), self.shadow_blur_input)
        form.addRow(self._t("annotations.shadow_offset_x"), self.shadow_offset_x_input)
        form.addRow(self._t("annotations.shadow_offset_y"), self.shadow_offset_y_input)
        return page

    def _build_geometry_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.x_fraction_input = self._number_input(0.0, 100.0, 50.0, decimals=1, suffix=" %")
        self.offset_x_input = self._number_input(-10000.0, 10000.0, 18.0, decimals=1, suffix=" px")
        self.offset_y_input = self._number_input(-10000.0, 10000.0, -36.0, decimals=1, suffix=" px")
        self.width_input = self._number_input(40.0, 4000.0, 220.0, decimals=1, suffix=" px")
        self.height_input = self._number_input(24.0, 4000.0, 76.0, decimals=1, suffix=" px")
        self.radius_input = self._number_input(0.0, 64.0, 6.0, decimals=1, suffix=" px")
        self.padding_input = self._number_input(0.0, 64.0, 7.0, decimals=1, suffix=" px")
        self.rotation_input = self._number_input(-180.0, 180.0, 0.0, decimals=1, suffix="°")
        form.addRow(self._t("annotations.x_position"), self.x_fraction_input)
        form.addRow(self._t("annotations.offset_x"), self.offset_x_input)
        form.addRow(self._t("annotations.offset_y"), self.offset_y_input)
        form.addRow(self._t("annotations.width"), self.width_input)
        form.addRow(self._t("annotations.height"), self.height_input)
        form.addRow(self._t("annotations.corner_radius"), self.radius_input)
        form.addRow(self._t("annotations.padding"), self.padding_input)
        form.addRow(self._t("annotations.rotation"), self.rotation_input)
        drag_hint = QLabel(self._t("annotations.drag_hint"))
        drag_hint.setWordWrap(True)
        drag_hint.setStyleSheet("color:#475569; padding-top:8px;")
        form.addRow("", drag_hint)
        return page

    def _build_actions(self) -> QHBoxLayout:
        actions = QHBoxLayout()
        add_button = QPushButton(self._t("common.add"))
        add_button.setObjectName("annotation-add-button")
        update_button = QPushButton(self._t("common.update"))
        update_button.setObjectName("annotation-update-button")
        duplicate_button = QPushButton(self._t("annotations.duplicate_action"))
        remove_button = QPushButton(self._t("common.remove"))
        remove_button.setObjectName("annotation-remove-button")
        self.undo_button = QPushButton(self._t("common.undo"))
        self.redo_button = QPushButton(self._t("common.redo"))
        add_button.clicked.connect(self._add)
        update_button.clicked.connect(self._update)
        duplicate_button.clicked.connect(self._duplicate)
        remove_button.clicked.connect(self._remove)
        self.undo_button.clicked.connect(self._undo)
        self.redo_button.clicked.connect(self._redo)
        actions.addWidget(add_button)
        actions.addWidget(update_button)
        actions.addWidget(duplicate_button)
        actions.addWidget(remove_button)
        actions.addStretch(1)
        actions.addWidget(self.undo_button)
        actions.addWidget(self.redo_button)
        return actions

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    @staticmethod
    def _number_input(
        minimum: float,
        maximum: float,
        value: float,
        *,
        decimals: int,
        suffix: str = "",
    ) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(decimals)
        widget.setValue(value)
        widget.setSuffix(suffix)
        return widget

    def _style_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.addItem(self._t("annotations.line_solid"), "solid")
        combo.addItem(self._t("annotations.line_dash"), "dash")
        combo.addItem(self._t("annotations.line_dot"), "dot")
        return combo

    def _refresh_tracks_and_curves(self) -> None:
        selected_track = self.track_input.currentData()
        self.track_input.clear()
        self.track_input.addItem(self._t("annotations.all_tracks"), None)
        layout = self.controller.session.current_tablet_layout
        if layout is not None:
            for track in layout.tracks:
                self.track_input.addItem(track.title, track.track_id)
        self._set_combo_data(self.track_input, selected_track)

        selected_parameter = self.parameter_input.currentData()
        self.parameter_input.clear()
        self.parameter_input.addItem(self._t("common.unset"), None)
        dataset = self.controller.session.current_dataset
        self.axis_id_input.blockSignals(True)
        self.axis_id_input.clear()
        if dataset is not None:
            mnemonics = sorted(
                {curve.metadata.original_mnemonic for curve in dataset.curves.values()}
            )
            for mnemonic in mnemonics:
                self.parameter_input.addItem(mnemonic, mnemonic)
            finite_depth = dataset.depth[np.isfinite(dataset.depth)]
            if finite_depth.size:
                minimum = float(np.min(finite_depth))
                maximum = float(np.max(finite_depth))
                self.depth_input.setRange(minimum, maximum)
                if not self._initial_values:
                    self.depth_input.setValue((minimum + maximum) / 2.0)

            for index in dataset.indexes.values():
                if index.role not in {IndexRole.DEPTH, IndexRole.TIME}:
                    continue
                unit = f", {index.unit}" if index.unit else ""
                role = self._t(
                    "annotations.axis_time"
                    if index.role is IndexRole.TIME
                    else "annotations.axis_depth"
                )
                self.axis_id_input.addItem(
                    f"{index.mnemonic}{unit} — {role}", index.index_id
                )
            preferred_axis = self._axis_id
            if preferred_axis is None and layout is not None:
                preferred_axis = layout.vertical_index_id
            if preferred_axis is None:
                preferred_axis = dataset.active_index.index_id
            self._set_combo_data(self.axis_id_input, preferred_axis)
        self.axis_id_input.blockSignals(False)
        self._axis_selection_changed()
        self._set_combo_data(self.parameter_input, selected_parameter)

    def _refresh(self) -> None:
        annotations = self.controller.available_annotations()
        self.table.setRowCount(len(annotations))
        for row, annotation in enumerate(annotations):
            depth_text = "—" if annotation.depth is None else f"{annotation.depth:g}"
            depth_item = QTableWidgetItem(depth_text)
            depth_item.setData(Qt.ItemDataRole.UserRole, annotation.annotation_id)
            self.table.setItem(row, 0, depth_item)
            self.table.setItem(row, 1, QTableWidgetItem(annotation.text))
            self.table.setItem(row, 2, QTableWidgetItem(self._kind_text(annotation.kind)))
            self.table.setItem(
                row,
                3,
                QTableWidgetItem(
                    annotation.track_id or self._t("annotations.all_tracks")
                ),
            )
            self.table.setItem(row, 4, QTableWidgetItem(self._anchor_text(annotation.anchor)))
            self.table.setItem(
                row,
                5,
                QTableWidgetItem(
                    self._t("common.yes") if annotation.print_enabled else self._t("common.no")
                ),
            )
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        if hasattr(self, "undo_button"):
            self.undo_button.setEnabled(self.controller.history.can_undo)
        if hasattr(self, "redo_button"):
            self.redo_button.setEnabled(self.controller.history.can_redo)

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        depth_item = self.table.item(row, 0) if row >= 0 else None
        if depth_item is None:
            return None
        value = depth_item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    def _select_annotation(self, annotation_id: str) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == annotation_id:
                self.table.selectRow(row)
                self._load_selected()
                return

    def _load_selected(self) -> None:
        annotation_id = self._selected_id()
        if annotation_id is None:
            return
        try:
            record = self.controller.get(annotation_id)
        except KeyError:
            return
        self._load_record(record)

    def _load_record(self, record: AnnotationRecord) -> None:
        self._set_combo_data(self.kind_input, record.kind.value)
        self._set_combo_data(self.anchor_input, record.anchor.value)
        self._set_combo_data(self.track_input, record.track_id)
        self._set_combo_data(self.parameter_input, record.parameter_mnemonic)
        self._set_combo_data(self.axis_id_input, record.axis_id)
        if record.depth is not None:
            self.depth_input.setValue(record.depth)
        if record.axis_value is not None:
            self.axis_input.setValue(record.axis_value)
        self.text_input.setText(record.text)
        self.x_fraction_input.setValue(record.x_fraction * 100.0)
        self.offset_x_input.setValue(record.offset_x)
        self.offset_y_input.setValue(record.offset_y)
        self.width_input.setValue(record.width)
        self.height_input.setValue(record.height)
        self.visible_input.setChecked(record.visible)
        self.locked_input.setChecked(record.locked)
        self.print_input.setChecked(record.print_enabled)
        self._asset_ref = record.asset_ref
        self._axis_id = record.axis_id
        self._parameter_value = record.parameter_value
        self._unit = record.unit
        self.asset_name.setText(self._asset_display_name(record.asset_ref))
        self._load_style(record.style)
        self._update_field_visibility()

    def _load_style(self, style: AnnotationStyle) -> None:
        self.font_input.setCurrentFont(QFont(style.font_family))
        self.font_size_input.setValue(style.font_size)
        self.bold_input.setChecked(style.bold)
        self.italic_input.setChecked(style.italic)
        self.underline_input.setChecked(style.underline)
        self.text_color_input.set_color(style.text_color)
        self.fill_color_input.set_color(style.fill_color)
        self.border_color_input.set_color(style.border_color)
        self.leader_color_input.set_color(style.leader_color)
        self.fill_opacity_input.setValue(style.fill_opacity)
        self.border_width_input.setValue(style.border_width)
        self.leader_width_input.setValue(style.leader_width)
        self._set_combo_data(self.border_style_input, style.border_style)
        self._set_combo_data(self.leader_style_input, style.leader_style)
        self._set_combo_data(self.arrow_input, style.arrow_style)
        self._set_combo_data(self.alignment_input, style.alignment)
        self._set_combo_data(self.vertical_alignment_input, style.vertical_alignment)
        self.shadow_input.setChecked(style.shadow)
        self.shadow_blur_input.setValue(style.shadow_blur)
        self.shadow_offset_x_input.setValue(style.shadow_offset_x)
        self.shadow_offset_y_input.setValue(style.shadow_offset_y)
        self.radius_input.setValue(style.corner_radius)
        self.padding_input.setValue(style.padding)
        self.rotation_input.setValue(style.rotation)

    def _style(self) -> AnnotationStyle:
        return AnnotationStyle(
            font_family=self.font_input.currentFont().family(),
            font_size=self.font_size_input.value(),
            bold=self.bold_input.isChecked(),
            italic=self.italic_input.isChecked(),
            underline=self.underline_input.isChecked(),
            text_color=self.text_color_input.color,
            fill_color=self.fill_color_input.color,
            fill_opacity=self.fill_opacity_input.value(),
            border_color=self.border_color_input.color,
            border_width=self.border_width_input.value(),
            border_style=str(self.border_style_input.currentData()),
            corner_radius=self.radius_input.value(),
            padding=self.padding_input.value(),
            alignment=str(self.alignment_input.currentData()),
            vertical_alignment=str(self.vertical_alignment_input.currentData()),
            leader_color=self.leader_color_input.color,
            leader_width=self.leader_width_input.value(),
            leader_style=str(self.leader_style_input.currentData()),
            arrow_style=str(self.arrow_input.currentData()),
            shadow=self.shadow_input.isChecked(),
            shadow_blur=self.shadow_blur_input.value(),
            shadow_offset_x=self.shadow_offset_x_input.value(),
            shadow_offset_y=self.shadow_offset_y_input.value(),
            rotation=self.rotation_input.value(),
        )

    @staticmethod
    def _initial_float(value: object) -> float:
        """Preserve Qt-friendly numeric coercion while keeping the boundary typed."""

        return float(cast(Any, value))

    def _values(self) -> _AnnotationValues:
        kind = AnnotationKind(str(self.kind_input.currentData()))
        anchor = AnnotationAnchor(str(self.anchor_input.currentData()))
        parameter = self.parameter_input.currentData()
        return {
            "kind": kind,
            "anchor": anchor,
            "text": self.text_input.toPlainText(),
            "track_id": self.track_input.currentData(),
            "depth": self.depth_input.value(),
            "axis_value": self.axis_input.value() if anchor is AnnotationAnchor.TIME else None,
            "axis_id": (
                str(self.axis_id_input.currentData())
                if self.axis_id_input.currentData()
                else self._axis_id
            ),
            "parameter_mnemonic": str(parameter) if parameter else None,
            "parameter_value": self._parameter_value,
            "unit": self._unit,
            "x_fraction": self.x_fraction_input.value() / 100.0,
            "offset_x": self.offset_x_input.value(),
            "offset_y": self.offset_y_input.value(),
            "width": self.width_input.value(),
            "height": self.height_input.value(),
            "style": self._style(),
            "asset_ref": self._asset_ref,
            "visible": self.visible_input.isChecked(),
            "locked": self.locked_input.isChecked(),
            "print_enabled": self.print_input.isChecked(),
        }

    def _save_single_item(self) -> None:
        """Create/update one annotation and close the focused editor.

        Toolbar/context-menu creation must behave like a normal editor dialog:
        enter text, adjust style/geometry, press Save.  The full manager keeps
        its Add/Update/Duplicate workflow, while direct editing no longer asks
        the user to discover a separate Add button at the bottom of a list.
        """

        saved: AnnotationRecord | None = None

        def operation() -> None:
            nonlocal saved
            if self._editing_annotation_id is None:
                saved = self.controller.add_annotation(**self._values())
            else:
                saved = self.controller.update_annotation(
                    self._editing_annotation_id, **self._values()
                )

        if not self._run(operation):
            return
        if saved is not None:
            self.result_annotation_id = saved.annotation_id
        self.accept()

    def _delete_single_item(self) -> None:
        annotation_id = self._editing_annotation_id
        if annotation_id is None:
            return
        answer = QMessageBox.question(
            self,
            self._t("annotations.title"),
            self._t("annotations.delete_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if not self._run(lambda: self.controller.remove(annotation_id)):
            return
        self.result_annotation_id = None
        self.accept()

    def _add(self) -> None:
        created: AnnotationRecord | None = None

        def operation() -> None:
            nonlocal created
            created = self.controller.add_annotation(**self._values())

        if self._run(operation):
            if created is not None:
                self._select_annotation(created.annotation_id)
            if AnnotationKind(str(self.kind_input.currentData())) not in {
                AnnotationKind.IMAGE,
                AnnotationKind.SYMBOL,
            }:
                self.text_input.clear()

    def _update(self) -> None:
        annotation_id = self._selected_id()
        if annotation_id is None:
            self._select_first_message()
            return
        self._run(lambda: self.controller.update_annotation(annotation_id, **self._values()))
        self._select_annotation(annotation_id)

    def _duplicate(self) -> None:
        annotation_id = self._selected_id()
        if annotation_id is None:
            self._select_first_message()
            return
        created: AnnotationRecord | None = None

        def operation() -> None:
            nonlocal created
            created = self.controller.duplicate(annotation_id)

        if self._run(operation) and created is not None:
            self._select_annotation(created.annotation_id)

    def _remove(self) -> None:
        annotation_id = self._selected_id()
        if annotation_id is None:
            self._select_first_message()
            return
        answer = QMessageBox.question(
            self,
            self._t("annotations.title"),
            self._t("annotations.delete_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self._run(lambda: self.controller.remove(annotation_id)):
            self.table.clearSelection()

    def _undo(self) -> None:
        self._run(self.controller.undo)

    def _redo(self) -> None:
        self._run(self.controller.redo)

    def _run(self, operation: Callable[[], object]) -> bool:
        try:
            operation()
        except (ImageAssetError, KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("annotations.title"), str(exc))
            return False
        self._refresh()
        self.annotations_changed.emit()
        return True

    def _choose_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self._t("annotations.choose_image"),
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.svg)",
        )
        if not filename:
            return
        try:
            asset = self.controller.install_image(Path(filename))
        except ImageAssetError as exc:
            QMessageBox.warning(self, self._t("annotations.title"), str(exc))
            return
        self._asset_ref = asset.asset_id
        self.asset_name.setText(asset.original_name)
        if AnnotationKind(str(self.kind_input.currentData())) not in {
            AnnotationKind.IMAGE,
            AnnotationKind.SYMBOL,
        }:
            self._set_combo_data(self.kind_input, AnnotationKind.IMAGE.value)
        self._update_field_visibility()

    def _clear_image(self) -> None:
        self._asset_ref = None
        self.asset_name.clear()

    def _asset_display_name(self, asset_ref: str | None) -> str:
        if not asset_ref:
            return ""
        asset = self.controller.session.image_assets.get(asset_ref)
        return asset.original_name if asset is not None else asset_ref

    def _apply_style_preset(self) -> None:
        preset = STYLE_PRESETS.get(str(self.preset_input.currentData()))
        if preset is not None:
            self._load_style(preset)

    def _update_field_visibility(self) -> None:
        anchor = AnnotationAnchor(str(self.anchor_input.currentData()))
        kind = AnnotationKind(str(self.kind_input.currentData()))
        self.parameter_input.setEnabled(anchor is AnnotationAnchor.CURVE)
        self.axis_id_input.setEnabled(anchor is AnnotationAnchor.TIME)
        self.axis_input.setEnabled(anchor is AnnotationAnchor.TIME)
        self.axis_display.setEnabled(anchor is AnnotationAnchor.TIME)
        self.asset_name.setEnabled(kind in {AnnotationKind.IMAGE, AnnotationKind.SYMBOL})
        self._refresh_axis_display()

    def _apply_initial_values(self) -> None:
        values = self._initial_values
        if not values:
            return
        if values.get("kind") is not None:
            self._set_combo_data(self.kind_input, str(values["kind"]))
        if values.get("anchor") is not None:
            self._set_combo_data(self.anchor_input, str(values["anchor"]))
        if values.get("track_id") is not None:
            self._set_combo_data(self.track_input, values["track_id"])
        if values.get("parameter_mnemonic") is not None:
            self._set_combo_data(self.parameter_input, values["parameter_mnemonic"])
        if values.get("axis_id") is not None:
            self._set_combo_data(self.axis_id_input, values["axis_id"])
        if values.get("depth") is not None:
            self.depth_input.setValue(self._initial_float(values["depth"]))
        if values.get("axis_value") is not None:
            self.axis_input.setValue(self._initial_float(values["axis_value"]))
        if values.get("x_fraction") is not None:
            self.x_fraction_input.setValue(
                self._initial_float(values["x_fraction"]) * 100.0
            )
        if values.get("offset_x") is not None:
            self.offset_x_input.setValue(self._initial_float(values["offset_x"]))
        if values.get("offset_y") is not None:
            self.offset_y_input.setValue(self._initial_float(values["offset_y"]))
        if values.get("width") is not None:
            self.width_input.setValue(self._initial_float(values["width"]))
        if values.get("height") is not None:
            self.height_input.setValue(self._initial_float(values["height"]))
        if values.get("text") is not None:
            self.text_input.setText(str(values["text"]))
        self._update_field_visibility()

    def _select_first_message(self) -> None:
        QMessageBox.information(
            self, self._t("annotations.title"), self._t("annotations.select_first")
        )

    def _kind_text(self, kind: AnnotationKind) -> str:
        return self._t(
            {
                AnnotationKind.CALLOUT: "annotations.kind_callout",
                AnnotationKind.COMMENT: "annotations.kind_comment",
                AnnotationKind.VALUE: "annotations.kind_value",
                AnnotationKind.IMAGE: "annotations.kind_image",
                AnnotationKind.SYMBOL: "annotations.kind_symbol",
            }[kind]
        )

    def _anchor_text(self, anchor: AnnotationAnchor) -> str:
        return self._t(
            {
                AnnotationAnchor.DEPTH: "annotations.anchor_depth",
                AnnotationAnchor.TIME: "annotations.anchor_time",
                AnnotationAnchor.CURVE: "annotations.anchor_curve",
                AnnotationAnchor.TRACK: "annotations.anchor_track",
            }[anchor]
        )

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
