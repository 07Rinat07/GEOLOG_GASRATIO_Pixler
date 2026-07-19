from __future__ import annotations

from dataclasses import dataclass

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
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from geoworkbench.catalogs.sensors import SensorCatalog, active_sensor_catalog
from geoworkbench.domain.models import Dataset
from geoworkbench.forms.binding_editor import TrackBindingEditor
from geoworkbench.forms.editor import FormStructureEditor
from geoworkbench.forms.models import ParameterBinding
from geoworkbench.tablet.models import CurveLineStyle, XScale


@dataclass(frozen=True, slots=True)
class _CurveOption:
    mnemonic: str
    canonical: str
    display_name: str
    unit: str


class TrackContentEditorDialog(QDialog):
    """Edit ParameterBinding entries of one form track."""

    def __init__(
        self,
        structure: FormStructureEditor,
        track_id: str,
        parent=None,
        *,
        dataset: Dataset | None = None,
        catalog: SensorCatalog | None = None,
        language: str = "ru",
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.dataset = dataset
        self.catalog = catalog or active_sensor_catalog()
        self.editor = TrackBindingEditor(structure, track_id)
        self._loading = False
        self._color = "#2563eb"
        self.setWindowTitle(self._text("Содержимое дорожки", "Жол мазмұны", "Track content"))
        self.resize(1050, 650)

        root = QVBoxLayout(self)
        root.addWidget(QLabel(self.editor.track.title))

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [
                self._text("Название", "Атауы", "Name"),
                self._text("Параметр", "Параметр", "Parameter"),
                self._text("Кривая LAS", "LAS қисығы", "LAS curve"),
                self._text("Единица", "Өлшем", "Unit"),
                self._text("Цвет", "Түс", "Color"),
                self._text("Толщина", "Қалыңдық", "Width"),
                self._text("Стиль", "Стиль", "Style"),
                self._text("Шкала", "Шкала", "Scale"),
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._load_selection)
        root.addWidget(self.table, 1)

        toolbar = QHBoxLayout()
        self._button(toolbar, self._text("+ Параметр", "+ Параметр", "+ Parameter"), self._add_parameter)
        self._button(toolbar, self._text("+ Кривая LAS", "+ LAS қисығы", "+ LAS curve"), self._add_las_curve)
        self._button(toolbar, self._text("Удалить", "Жою", "Remove"), self._remove)
        self._button(toolbar, "↑", lambda: self._move(-1))
        self._button(toolbar, "↓", lambda: self._move(1))
        root.addLayout(toolbar)

        properties = QFormLayout()
        self.name_edit = QLineEdit()
        properties.addRow(self._text("Отображаемое имя", "Көрсетілетін атау", "Display name"), self.name_edit)

        self.canonical_combo = QComboBox()
        self.canonical_combo.setEditable(True)
        for sensor in sorted(self.catalog.sensors, key=lambda item: item.canonical_mnemonic.casefold()):
            label = f"{sensor.canonical_mnemonic} — {sensor.name_ru}"
            self.canonical_combo.addItem(label, sensor.canonical_mnemonic)
        properties.addRow(self._text("Канонический параметр", "Канондық параметр", "Canonical parameter"), self.canonical_combo)

        self.source_combo = QComboBox()
        self.source_combo.setEditable(True)
        self.source_combo.addItem("", None)
        if dataset is not None:
            for curve in dataset.curves.values():
                metadata = curve.metadata
                label = metadata.original_mnemonic
                if metadata.description:
                    label += f" — {metadata.description}"
                self.source_combo.addItem(label, metadata.original_mnemonic)
        properties.addRow(self._text("Кривая LAS", "LAS қисығы", "LAS curve"), self.source_combo)

        self.unit_edit = QLineEdit()
        properties.addRow(self._text("Единица", "Өлшем", "Unit"), self.unit_edit)

        self.visible_check = QCheckBox(self._text("Показывать кривую", "Қисықты көрсету", "Show curve"))
        properties.addRow("", self.visible_check)

        color_row = QHBoxLayout()
        self.color_edit = QLineEdit()
        color_row.addWidget(self.color_edit)
        color_button = QPushButton(self._text("Выбрать", "Таңдау", "Choose"))
        color_button.clicked.connect(self._choose_color)
        color_row.addWidget(color_button)
        properties.addRow(self._text("Цвет", "Түс", "Color"), color_row)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.5, 10.0)
        self.width_spin.setSingleStep(0.25)
        self.width_spin.setSuffix(" px")
        properties.addRow(self._text("Толщина", "Қалыңдық", "Width"), self.width_spin)

        self.line_style_combo = QComboBox()
        for style in CurveLineStyle:
            self.line_style_combo.addItem(style.value, style)
        properties.addRow(self._text("Стиль линии", "Сызық стилі", "Line style"), self.line_style_combo)

        self.scale_combo = QComboBox()
        for scale in XScale:
            self.scale_combo.addItem(scale.value, scale)
        self.scale_combo.currentIndexChanged.connect(self._range_state)
        properties.addRow(self._text("Шкала", "Шкала", "Scale"), self.scale_combo)

        self.auto_range_check = QCheckBox(self._text("Автоматический диапазон", "Автоматты диапазон", "Automatic range"))
        self.auto_range_check.toggled.connect(self._range_state)
        properties.addRow("", self.auto_range_check)

        range_row = QHBoxLayout()
        self.min_spin = QDoubleSpinBox()
        self.max_spin = QDoubleSpinBox()
        for spin in (self.min_spin, self.max_spin):
            spin.setRange(-1.0e12, 1.0e12)
            spin.setDecimals(6)
        range_row.addWidget(self.min_spin)
        range_row.addWidget(QLabel("…"))
        range_row.addWidget(self.max_spin)
        properties.addRow(self._text("Диапазон", "Диапазон", "Range"), range_row)
        root.addLayout(properties)

        apply_row = QHBoxLayout()
        apply_button = QPushButton(self._text("Применить свойства", "Қасиеттерді қолдану", "Apply properties"))
        apply_button.clicked.connect(self._apply_properties)
        apply_row.addStretch(1)
        apply_row.addWidget(apply_button)
        root.addLayout(apply_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._text("Готово", "Дайын", "Done"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self._text("Отмена", "Бас тарту", "Cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._reload()

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {"ru": ru, "kk": kk, "en": en}.get(self.language, ru)

    def _button(self, layout: QHBoxLayout, caption: str, callback) -> QPushButton:
        button = QPushButton(caption)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def _selected_binding(self) -> ParameterBinding | None:
        row = self.table.currentRow()
        bindings = self.editor.bindings
        return bindings[row] if 0 <= row < len(bindings) else None

    def _reload(self, binding_id: str | None = None) -> None:
        self._loading = True
        try:
            self.table.setRowCount(0)
            selected_row = -1
            for row, binding in enumerate(self.editor.bindings):
                self.table.insertRow(row)
                values = (
                    binding.display_name,
                    binding.canonical_parameter_id,
                    binding.source_mnemonic or "—",
                    binding.unit or "—",
                    binding.style.color,
                    f"{binding.style.width:g}",
                    binding.style.line_style.value,
                    binding.x_scale.value,
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(row, column, item)
                if binding.binding_id == binding_id:
                    selected_row = row
            self.table.resizeColumnsToContents()
            if selected_row >= 0:
                self.table.selectRow(selected_row)
            elif self.table.rowCount():
                self.table.selectRow(0)
            else:
                self._clear_properties()
        finally:
            self._loading = False
        self._load_selection()

    def _clear_properties(self) -> None:
        self.name_edit.clear()
        self.canonical_combo.setCurrentText("")
        self.source_combo.setCurrentIndex(0)
        self.unit_edit.clear()
        self.visible_check.setChecked(True)
        self.color_edit.setText("#2563eb")
        self.width_spin.setValue(1.5)
        self.line_style_combo.setCurrentIndex(0)
        self.scale_combo.setCurrentIndex(0)
        self.auto_range_check.setChecked(True)
        self.min_spin.setValue(0.0)
        self.max_spin.setValue(1.0)
        self._range_state()

    def _load_selection(self) -> None:
        if self._loading:
            return
        binding = self._selected_binding()
        if binding is None:
            self._clear_properties()
            return
        self._loading = True
        try:
            self.name_edit.setText(binding.display_name)
            index = self.canonical_combo.findData(binding.canonical_parameter_id)
            if index >= 0:
                self.canonical_combo.setCurrentIndex(index)
            else:
                self.canonical_combo.setCurrentText(binding.canonical_parameter_id)
            source_index = self.source_combo.findData(binding.source_mnemonic)
            if source_index >= 0:
                self.source_combo.setCurrentIndex(source_index)
            else:
                self.source_combo.setCurrentText(binding.source_mnemonic or "")
            self.unit_edit.setText(binding.unit)
            self.visible_check.setChecked(binding.visible)
            self.color_edit.setText(binding.style.color)
            self.width_spin.setValue(binding.style.width)
            style_index = self.line_style_combo.findData(binding.style.line_style)
            if style_index >= 0:
                self.line_style_combo.setCurrentIndex(style_index)
            scale_index = self.scale_combo.findData(binding.x_scale)
            if scale_index >= 0:
                self.scale_combo.setCurrentIndex(scale_index)
            automatic = binding.x_min is None
            self.auto_range_check.setChecked(automatic)
            if not automatic:
                self.min_spin.setValue(binding.x_min or 0.0)
                self.max_spin.setValue(binding.x_max or 1.0)
            self._range_state()
        finally:
            self._loading = False

    def _canonical_value(self) -> str:
        data = self.canonical_combo.currentData()
        if isinstance(data, str) and data:
            return data
        text = self.canonical_combo.currentText().split(" — ", 1)[0].strip()
        return text

    def _source_value(self) -> str | None:
        data = self.source_combo.currentData()
        if isinstance(data, str) and data:
            return data
        text = self.source_combo.currentText().split(" — ", 1)[0].strip()
        return text or None

    def _choose_color(self) -> None:
        initial = QColor(self.color_edit.text())
        color = QColorDialog.getColor(initial if initial.isValid() else QColor("#2563eb"), self)
        if color.isValid():
            self.color_edit.setText(color.name())

    def _range_state(self) -> None:
        enabled = not self.auto_range_check.isChecked()
        self.min_spin.setEnabled(enabled)
        self.max_spin.setEnabled(enabled)

    def _add_parameter(self) -> None:
        choices = sorted(
            self.catalog.sensors,
            key=lambda item: (item.category, item.canonical_mnemonic.casefold()),
        )
        labels = [f"{item.canonical_mnemonic} — {item.name_ru}" for item in choices]
        selected, ok = QInputDialog.getItem(
            self,
            self.windowTitle(),
            self._text("Параметр", "Параметр", "Parameter"),
            labels,
            editable=False,
        )
        if not ok or not selected:
            return
        definition = choices[labels.index(selected)]
        try:
            binding = self.editor.add(
                definition.canonical_mnemonic,
                definition.name_ru or definition.canonical_mnemonic,
                unit=definition.unit,
                color=definition.color,
                x_min=definition.default_min,
                x_max=definition.default_max,
            )
        except (PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self._reload(binding.binding_id)

    def _curve_options(self) -> list[_CurveOption]:
        if self.dataset is None:
            return []
        result: list[_CurveOption] = []
        for curve in self.dataset.curves.values():
            metadata = curve.metadata
            match = self.catalog.match(
                metadata.original_mnemonic,
                description=metadata.description or "",
                unit=metadata.unit or "",
            )
            canonical = (
                match.definition.canonical_mnemonic
                if match is not None
                else metadata.canonical_mnemonic or metadata.original_mnemonic
            )
            display = (
                match.definition.name_ru
                if match is not None
                else metadata.description or metadata.original_mnemonic
            )
            result.append(
                _CurveOption(
                    metadata.original_mnemonic,
                    canonical,
                    display,
                    metadata.unit or "",
                )
            )
        return sorted(result, key=lambda item: item.mnemonic.casefold())

    def _add_las_curve(self) -> None:
        options = self._curve_options()
        if not options:
            QMessageBox.information(
                self,
                self.windowTitle(),
                self._text("Сначала откройте LAS-файл.", "Алдымен LAS файлын ашыңыз.", "Open a LAS file first."),
            )
            return
        labels = [f"{item.mnemonic} — {item.display_name}" for item in options]
        selected, ok = QInputDialog.getItem(
            self,
            self.windowTitle(),
            self._text("Кривая LAS", "LAS қисығы", "LAS curve"),
            labels,
            editable=False,
        )
        if not ok or not selected:
            return
        option = options[labels.index(selected)]
        try:
            binding = self.editor.add(
                option.canonical,
                option.display_name,
                source_mnemonic=option.mnemonic,
                unit=option.unit,
            )
        except (PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self._reload(binding.binding_id)

    def _remove(self) -> None:
        binding = self._selected_binding()
        if binding is None:
            return
        try:
            self.editor.remove(binding.binding_id)
        except (KeyError, PermissionError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self._reload()

    def _move(self, delta: int) -> None:
        binding = self._selected_binding()
        if binding is None:
            return
        row = self.table.currentRow()
        try:
            self.editor.move(binding.binding_id, row + delta)
        except (KeyError, PermissionError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self._reload(binding.binding_id)

    def _apply_properties(self) -> None:
        binding = self._selected_binding()
        if binding is None:
            return
        x_min = None if self.auto_range_check.isChecked() else self.min_spin.value()
        x_max = None if self.auto_range_check.isChecked() else self.max_spin.value()
        try:
            updated = self.editor.update(
                binding.binding_id,
                canonical_parameter_id=self._canonical_value(),
                display_name=self.name_edit.text().strip(),
                source_mnemonic=self._source_value(),
                unit=self.unit_edit.text().strip(),
                visible=self.visible_check.isChecked(),
                color=self.color_edit.text().strip(),
                width=self.width_spin.value(),
                line_style=self.line_style_combo.currentData(),
                x_scale=self.scale_combo.currentData(),
                x_min=x_min,
                x_max=x_max,
            )
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self._reload(updated.binding_id)
