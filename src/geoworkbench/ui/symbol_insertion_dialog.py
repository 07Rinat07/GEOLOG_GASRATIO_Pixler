from __future__ import annotations

from math import isfinite

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.form_constructor.asset_install import (
    factory_symbol_variant_path,
    load_factory_constructor_registry,
)
from geoworkbench.form_constructor.asset_registry import AssetDefinition
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.symbol_insertion import SymbolInsertionSelection
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.tablet.models import TrackKind


class SymbolInsertionDialog(QDialog):
    """Catalog picker and data-anchor editor for graph symbols."""

    def __init__(
        self,
        controller: DepthAnnotationController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        initial_values: dict[str, object] | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.localizer = Localizer.create(language)
        self.language = language
        self._initial_values = dict(initial_values or {})
        self._registry = load_factory_constructor_registry()
        self.selection: SymbolInsertionSelection | None = None

        self.setObjectName("symbol-insertion-dialog")
        self.setWindowTitle(self._t("symbol_insert.title"))
        self.resize(980, 680)

        root = QVBoxLayout(self)
        hint = QLabel(self._t("symbol_insert.hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "background:#eff6ff; border:1px solid #93c5fd; border-radius:6px; "
            "padding:8px 10px; color:#1e3a8a;"
        )
        root.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_catalog_panel())
        splitter.addWidget(self._build_placement_panel())
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        root.addWidget(splitter, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._t("symbol_insert.insert")
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            self._t("common.cancel")
        )
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._populate_tracks()
        self._apply_initial_values()
        self._refresh_catalog()

    def _build_catalog_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("symbol-catalog-search")
        self.search_input.setPlaceholderText(self._t("symbol_insert.search_placeholder"))
        self.search_input.textChanged.connect(self._refresh_catalog)
        layout.addWidget(self.search_input)

        self.symbol_table = QTableWidget(0, 3)
        self.symbol_table.setObjectName("symbol-catalog-table")
        self.symbol_table.setHorizontalHeaderLabels(
            [
                self._t("symbol_insert.preview"),
                self._t("symbol_insert.name"),
                self._t("symbol_insert.category"),
            ]
        )
        self.symbol_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.symbol_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.symbol_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.symbol_table.setIconSize(QSize(52, 52))
        self.symbol_table.verticalHeader().setVisible(False)
        header = self.symbol_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.symbol_table.itemSelectionChanged.connect(self._symbol_selection_changed)
        self.symbol_table.itemDoubleClicked.connect(lambda _item: self._accept_selection())
        layout.addWidget(self.symbol_table, 1)
        return panel

    def _build_placement_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 0, 0, 0)

        self.preview = QLabel(self._t("symbol_insert.select_symbol"))
        self.preview.setObjectName("symbol-insertion-preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(180)
        self.preview.setStyleSheet(
            "QLabel { background:#f8fafc; border:1px solid #cbd5e1; "
            "border-radius:8px; padding:10px; }"
        )
        layout.addWidget(self.preview)

        form = QFormLayout()
        self.transparent_input = QCheckBox(self._t("symbol_insert.transparent"))
        self.transparent_input.setObjectName("symbol-transparent-checkbox")
        self.transparent_input.setChecked(True)
        self.transparent_input.toggled.connect(self._refresh_preview)
        form.addRow("", self.transparent_input)

        self.track_input = QComboBox()
        self.track_input.setObjectName("symbol-track-input")
        self.track_input.currentIndexChanged.connect(self._populate_parameters)
        form.addRow(self._t("symbol_insert.track"), self.track_input)

        self.parameter_input = QComboBox()
        self.parameter_input.setObjectName("symbol-parameter-input")
        form.addRow(self._t("symbol_insert.parameter"), self.parameter_input)

        self.depth_input = QDoubleSpinBox()
        self.depth_input.setObjectName("symbol-depth-input")
        self.depth_input.setDecimals(4)
        self.depth_input.setSingleStep(0.1)
        self._configure_depth_range()
        form.addRow(self._t("symbol_insert.depth"), self.depth_input)

        self.width_input = self._size_input("symbol-width-input")
        self.height_input = self._size_input("symbol-height-input")
        form.addRow(self._t("symbol_insert.width"), self.width_input)
        form.addRow(self._t("symbol_insert.height"), self.height_input)
        layout.addLayout(form)

        note = QLabel(self._t("symbol_insert.mouse_hint"))
        note.setWordWrap(True)
        note.setStyleSheet("color:#475569; padding-top:6px;")
        layout.addWidget(note)
        layout.addStretch(1)
        return panel

    @staticmethod
    def _size_input(object_name: str) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setObjectName(object_name)
        control.setRange(24.0, 1200.0)
        control.setDecimals(1)
        control.setSingleStep(4.0)
        control.setSuffix(" px")
        return control

    def _configure_depth_range(self) -> None:
        dataset = self.controller.session.current_dataset
        if dataset is None:
            self.depth_input.setRange(-1_000_000_000.0, 1_000_000_000.0)
            return
        finite = dataset.depth[np.isfinite(dataset.depth)]
        if finite.size:
            minimum = float(np.min(finite))
            maximum = float(np.max(finite))
            self.depth_input.setRange(minimum, maximum)
            self.depth_input.setValue((minimum + maximum) / 2.0)
        else:
            self.depth_input.setRange(-1_000_000_000.0, 1_000_000_000.0)

    def _populate_tracks(self) -> None:
        self.track_input.clear()
        layout = self.controller.session.current_tablet_layout
        tracks = tuple(getattr(layout, "tracks", ())) if layout is not None else ()
        for track in tracks:
            if track.kind is TrackKind.DEPTH or not track.visible:
                continue
            title = track.title.strip() or track.track_id
            self.track_input.addItem(title, track.track_id)
        initial_track = self._initial_values.get("track_id")
        if self.track_input.count() == 0 and isinstance(initial_track, str) and initial_track:
            self.track_input.addItem(initial_track, initial_track)
        self._populate_parameters()

    def _populate_parameters(self, _index: int | None = None) -> None:
        selected = self.parameter_input.currentData() if hasattr(self, "parameter_input") else None
        self.parameter_input.clear()
        self.parameter_input.addItem(self._t("symbol_insert.no_parameter"), None)
        track_id = self.track_input.currentData()
        layout = self.controller.session.current_tablet_layout
        if layout is not None and isinstance(track_id, str):
            try:
                track = layout.track_by_id(track_id)
            except KeyError:
                track = None
            if track is not None:
                dataset = self.controller.session.current_dataset
                for mnemonic in track.curve_mnemonics:
                    curve = dataset.curve_by_mnemonic(mnemonic) if dataset is not None else None
                    unit = f" [{curve.metadata.unit}]" if curve and curve.metadata.unit else ""
                    self.parameter_input.addItem(f"{mnemonic}{unit}", mnemonic)
        target = self._initial_values.get("parameter_mnemonic", selected)
        if isinstance(target, str):
            index = self.parameter_input.findData(target)
            if index >= 0:
                self.parameter_input.setCurrentIndex(index)
        self.parameter_input.setEnabled(self.parameter_input.count() > 1)

    def _apply_initial_values(self) -> None:
        track_id = self._initial_values.get("track_id")
        if isinstance(track_id, str):
            index = self.track_input.findData(track_id)
            if index >= 0:
                self.track_input.setCurrentIndex(index)
        self._populate_parameters()

        depth = self._finite_value(self._initial_values.get("depth"))
        if depth is not None:
            self.depth_input.setValue(depth)
        self.width_input.setValue(64.0)
        self.height_input.setValue(64.0)

    def _refresh_catalog(self, _text: str | None = None) -> None:
        selected_id = self.selected_asset.asset_id if self.selected_asset is not None else None
        matches = self._registry.search(
            self.search_input.text(),
            kind="depth_symbol",
            language=self.language.value,
        )
        self.symbol_table.setRowCount(len(matches))
        selected_row = -1
        for row, asset in enumerate(matches):
            preview_path = factory_symbol_variant_path(asset, transparent_background=True)
            icon_item = QTableWidgetItem()
            icon_item.setData(Qt.ItemDataRole.UserRole, asset.asset_id)
            icon_item.setIcon(QIcon(str(preview_path)))
            name_item = QTableWidgetItem(asset.display_name(self.language.value))
            name_item.setData(Qt.ItemDataRole.UserRole, asset.asset_id)
            category_item = QTableWidgetItem(self._category_name(asset.category))
            category_item.setData(Qt.ItemDataRole.UserRole, asset.asset_id)
            self.symbol_table.setItem(row, 0, icon_item)
            self.symbol_table.setItem(row, 1, name_item)
            self.symbol_table.setItem(row, 2, category_item)
            self.symbol_table.setRowHeight(row, 60)
            if asset.asset_id == selected_id:
                selected_row = row
        if selected_row < 0 and matches:
            selected_row = 0
        if selected_row >= 0:
            self.symbol_table.selectRow(selected_row)
        else:
            self.preview.setPixmap(QPixmap())
            self.preview.setText(self._t("symbol_insert.no_results"))

    @property
    def selected_asset(self) -> AssetDefinition | None:
        row = self.symbol_table.currentRow() if hasattr(self, "symbol_table") else -1
        if row < 0:
            return None
        item = self.symbol_table.item(row, 0)
        asset_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(asset_id, str):
            return None
        try:
            return self._registry.get(asset_id)
        except KeyError:
            return None

    def _symbol_selection_changed(self) -> None:
        asset = self.selected_asset
        if asset is not None:
            width, height = self._default_size(asset)
            self.width_input.setValue(width)
            self.height_input.setValue(height)
        self._refresh_preview()

    def _refresh_preview(self, _checked: bool | None = None) -> None:
        asset = self.selected_asset
        if asset is None:
            self.preview.setPixmap(QPixmap())
            self.preview.setText(self._t("symbol_insert.select_symbol"))
            return
        path = factory_symbol_variant_path(
            asset,
            transparent_background=self.transparent_input.isChecked(),
        )
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setText(self._t("symbol_insert.preview_failed"))
            return
        scaled = pixmap.scaled(
            QSize(220, 160),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setText("")
        self.preview.setPixmap(scaled)

    def _accept_selection(self) -> None:
        asset = self.selected_asset
        if asset is None:
            QMessageBox.information(
                self,
                self.windowTitle(),
                self._t("symbol_insert.select_symbol"),
            )
            return
        track_id = self.track_input.currentData()
        if not isinstance(track_id, str) or not track_id:
            QMessageBox.information(
                self,
                self.windowTitle(),
                self._t("symbol_insert.select_track"),
            )
            return
        width = float(self.width_input.value())
        height = float(self.height_input.value())
        x_fraction = self._bounded_initial("x_fraction", 0.5, 0.0, 1.0)
        default_offset_x = -width / 2.0
        default_offset_y = -height / 2.0
        self.selection = SymbolInsertionSelection(
            symbol=asset,
            transparent_background=self.transparent_input.isChecked(),
            track_id=track_id,
            parameter_mnemonic=(
                str(self.parameter_input.currentData())
                if isinstance(self.parameter_input.currentData(), str)
                else None
            ),
            depth=float(self.depth_input.value()),
            x_fraction=x_fraction,
            offset_x=default_offset_x,
            offset_y=default_offset_y,
            width=width,
            height=height,
        )
        self.accept()

    @staticmethod
    def _default_size(asset: AssetDefinition) -> tuple[float, float]:
        width = max(1.0, float(asset.width_px))
        height = max(1.0, float(asset.height_px))
        scale = 72.0 / max(width, height)
        return max(40.0, width * scale), max(28.0, height * scale)

    def _bounded_initial(
        self,
        name: str,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        value = self._finite_value(self._initial_values.get(name))
        if value is None:
            return default
        return max(minimum, min(maximum, value))

    @staticmethod
    def _finite_value(value: object) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        normalized = float(value)
        return normalized if isfinite(normalized) else None

    def _category_name(self, category: str) -> str:
        key = f"symbol_insert.category_{category.replace('-', '_')}"
        translated = self._t(key)
        return translated if translated != key else category

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)
