from __future__ import annotations

from copy import deepcopy

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import Dataset
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.parameter_labels import localized_curve_name
from geoworkbench.tablet.models import (
    CurveDisplaySettings,
    CurveLineStyle,
    CurveStyle,
    TrackDefinition,
    XScale,
)


class CurveSettingsDialog(QDialog):
    """Edit readable captions, scale and line style for every curve in one track."""

    def __init__(
        self,
        track: TrackDefinition,
        dataset: Dataset,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self._localizer = Localizer.create(language)
        self._track = track
        self._dataset = dataset
        self._styles = deepcopy(track.curve_styles)
        self._display = deepcopy(track.curve_display)
        self._current_mnemonic: str | None = None
        self._loading = False

        self.setWindowTitle(self._t("curve_settings.title"))
        self.resize(760, 500)
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        self.curves = QListWidget()
        self.curves.setMinimumWidth(240)
        for mnemonic in track.curve_mnemonics:
            curve = dataset.curve_by_mnemonic(mnemonic)
            metadata = curve.metadata if curve is not None else None
            settings = track.curve_display_settings(mnemonic)
            label = localized_curve_name(
                mnemonic,
                description=(metadata.description or "") if metadata is not None else "",
                unit=(metadata.unit or "") if metadata is not None else "",
                language=language,
                configured=settings.display_name,
            )
            item = QListWidgetItem(f"{label}  [{mnemonic}]")
            item.setData(Qt.ItemDataRole.UserRole, mnemonic)
            self.curves.addItem(item)
        splitter.addWidget(self.curves)

        editor = QWidget()
        form = QFormLayout(editor)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.mnemonic_label = QLabel("—")
        form.addRow(self._t("curve_settings.mnemonic"), self.mnemonic_label)

        self.display_name = QLineEdit()
        self.display_name.setMaxLength(120)
        form.addRow(self._t("curve_settings.display_name"), self.display_name)

        self.scale = QComboBox()
        self.scale.addItem(self._t("curve_settings.linear"), XScale.LINEAR.value)
        self.scale.addItem(self._t("curve_settings.logarithmic"), XScale.LOGARITHMIC.value)
        form.addRow(self._t("curve_settings.scale"), self.scale)

        self.auto_range = QCheckBox(self._t("curve_settings.auto_range"))
        form.addRow("", self.auto_range)

        self.minimum = QDoubleSpinBox()
        self.minimum.setDecimals(6)
        self.minimum.setRange(-1e12, 1e12)
        self.maximum = QDoubleSpinBox()
        self.maximum.setDecimals(6)
        self.maximum.setRange(-1e12, 1e12)
        range_row = QHBoxLayout()
        range_row.addWidget(self.minimum)
        range_row.addWidget(QLabel("…"))
        range_row.addWidget(self.maximum)
        form.addRow(self._t("curve_settings.range"), range_row)

        self.color_button = QPushButton()
        self.color_button.clicked.connect(self._choose_color)
        form.addRow(self._t("curve_settings.color"), self.color_button)

        self.width = QDoubleSpinBox()
        self.width.setDecimals(1)
        self.width.setSingleStep(0.5)
        self.width.setRange(0.5, 10.0)
        form.addRow(self._t("curve_settings.width"), self.width)

        self.line_style = QComboBox()
        self.line_style.addItem(self._t("curve_settings.style.solid"), CurveLineStyle.SOLID.value)
        self.line_style.addItem(self._t("curve_settings.style.dash"), CurveLineStyle.DASH.value)
        self.line_style.addItem(self._t("curve_settings.style.dot"), CurveLineStyle.DOT.value)
        self.line_style.addItem(
            self._t("curve_settings.style.dash_dot"), CurveLineStyle.DASH_DOT.value
        )
        form.addRow(self._t("curve_settings.line_style"), self.line_style)
        splitter.addWidget(editor)
        splitter.setStretchFactor(1, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._t("common.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self._t("common.cancel"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.curves.currentItemChanged.connect(self._curve_changed)
        self.auto_range.toggled.connect(self._range_mode_changed)
        if self.curves.count():
            self.curves.setCurrentRow(0)

    def _t(self, key: str, **values: object) -> str:
        return self._localizer.text(key, **values)

    @property
    def curve_styles(self) -> dict[str, CurveStyle]:
        return deepcopy(self._styles)

    @property
    def curve_display(self) -> dict[str, CurveDisplaySettings]:
        return deepcopy(self._display)

    def _curve_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        self._store_current()
        if current is None:
            self._current_mnemonic = None
            return
        mnemonic = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(mnemonic, str):
            return
        self._current_mnemonic = mnemonic
        self._load_current()

    def _load_current(self) -> None:
        mnemonic = self._current_mnemonic
        if mnemonic is None:
            return
        self._loading = True
        try:
            curve = self._dataset.curve_by_mnemonic(mnemonic)
            metadata = curve.metadata if curve is not None else None
            display = self._display.get(mnemonic, self._track.curve_display_settings(mnemonic))
            style = self._styles.get(mnemonic, self._track.curve_style(mnemonic) or CurveStyle())
            fallback_name = localized_curve_name(
                mnemonic,
                description=(metadata.description or "") if metadata is not None else "",
                unit=(metadata.unit or "") if metadata is not None else "",
                language=self._localizer.language,
                configured=display.display_name,
            )
            self.mnemonic_label.setText(mnemonic)
            self.display_name.setText(fallback_name)
            self.scale.setCurrentIndex(max(0, self.scale.findData(display.x_scale.value)))
            self.auto_range.setChecked(display.automatic_range)
            suggested = self._suggested_range(mnemonic, display.x_scale)
            minimum = display.x_min if display.x_min is not None else suggested[0]
            maximum = display.x_max if display.x_max is not None else suggested[1]
            self.minimum.setValue(minimum)
            self.maximum.setValue(maximum)
            self._set_color(style.color)
            self.width.setValue(style.width)
            self.line_style.setCurrentIndex(max(0, self.line_style.findData(style.line_style.value)))
            self._range_mode_changed(self.auto_range.isChecked())
        finally:
            self._loading = False

    def _store_current(self) -> None:
        mnemonic = self._current_mnemonic
        if mnemonic is None or self._loading:
            return
        scale = XScale(str(self.scale.currentData()))
        minimum = maximum = None
        if not self.auto_range.isChecked():
            minimum = float(self.minimum.value())
            maximum = float(self.maximum.value())
            if minimum >= maximum:
                return
            if scale is XScale.LOGARITHMIC and minimum <= 0:
                return
        self._display[mnemonic] = CurveDisplaySettings(
            display_name=self.display_name.text().strip() or mnemonic,
            x_scale=scale,
            x_min=minimum,
            x_max=maximum,
        )
        self._styles[mnemonic] = CurveStyle(
            color=str(self.color_button.property("curveColor") or "#2563eb"),
            width=float(self.width.value()),
            line_style=CurveLineStyle(str(self.line_style.currentData())),
        )
        self._update_item_label(mnemonic)

    def _accept(self) -> None:
        mnemonic = self._current_mnemonic
        if mnemonic is not None and not self.auto_range.isChecked():
            scale = XScale(str(self.scale.currentData()))
            minimum = float(self.minimum.value())
            maximum = float(self.maximum.value())
            invalid = minimum >= maximum or (scale is XScale.LOGARITHMIC and minimum <= 0)
            if invalid:
                QMessageBox.warning(
                    self,
                    self._t("curve_settings.title"),
                    self._t("curve_settings.invalid_range"),
                )
                return
        self._store_current()
        self.accept()

    def _update_item_label(self, mnemonic: str) -> None:
        display = self._display.get(mnemonic)
        if display is None:
            return
        for row in range(self.curves.count()):
            item = self.curves.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == mnemonic:
                item.setText(f"{display.display_name}  [{mnemonic}]")
                return

    def _range_mode_changed(self, automatic: bool) -> None:
        self.minimum.setEnabled(not automatic)
        self.maximum.setEnabled(not automatic)

    def _choose_color(self) -> None:
        initial = QColor(str(self.color_button.property("curveColor") or "#2563eb"))
        color = QColorDialog.getColor(initial, self, self._t("curve_settings.color"))
        if color.isValid():
            self._set_color(color.name())

    def _set_color(self, color: str) -> None:
        self.color_button.setProperty("curveColor", color)
        self.color_button.setText(color)
        self.color_button.setStyleSheet(
            f"QPushButton {{ background: {color}; color: {'#000000' if QColor(color).lightness() > 150 else '#ffffff'}; }}"
        )

    def _suggested_range(self, mnemonic: str, scale: XScale) -> tuple[float, float]:
        curve = self._dataset.curve_by_mnemonic(mnemonic)
        if curve is None:
            return (0.1, 100.0) if scale is XScale.LOGARITHMIC else (0.0, 100.0)
        values = np.asarray(curve.values, dtype=float)
        finite = values[np.isfinite(values)]
        if scale is XScale.LOGARITHMIC:
            finite = finite[finite > 0]
        if finite.size == 0:
            return (0.1, 100.0) if scale is XScale.LOGARITHMIC else (0.0, 100.0)
        minimum, maximum = (float(v) for v in np.nanpercentile(finite, [1.0, 99.0]))
        if minimum == maximum:
            padding = max(abs(minimum) * 0.05, 0.1)
            minimum -= padding
            maximum += padding
        if scale is XScale.LOGARITHMIC:
            minimum = max(minimum, float(np.min(finite)))
        return minimum, maximum
