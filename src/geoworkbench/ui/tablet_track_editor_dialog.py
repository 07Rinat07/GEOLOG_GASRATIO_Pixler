from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from geoworkbench.domain.text_presentation import (
    TEXT_ORIENTATIONS,
    TEXT_VERTICAL_POSITIONS,
)
from geoworkbench.tablet.models import (
    CurveDisplaySettings,
    CurveLineStyle,
    CurveStyle,
    TrackDefinition,
    TrackKind,
    XScale,
)


class TabletTrackEditorDialog(QDialog):
    """Edit every user-facing caption and curve presentation of one live track."""

    def __init__(self, track: TrackDefinition, parent=None, *, language: str = "ru") -> None:
        super().__init__(parent)
        self.language = language
        self.track = deepcopy(track)
        self._loading = False
        self.setWindowTitle(self._text("Редактор колонки/дорожки", "Баған/жол редакторы", "Column/track editor"))
        self.resize(1050, 680)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.title_input = QLineEdit(self.track.title)
        self.title_orientation_input = QComboBox()
        orientation_labels = {
            "horizontal": self._text("Горизонтально (0°)", "Көлденең (0°)", "Horizontal (0°)"),
            "vertical_bottom_to_top": self._text(
                "Вертикально снизу вверх (90°)",
                "Төменнен жоғары тік (90°)",
                "Vertical bottom to top (90°)",
            ),
            "vertical_top_to_bottom": self._text(
                "Вертикально сверху вниз (90°)",
                "Жоғарыдан төмен тік (90°)",
                "Vertical top to bottom (90°)",
            ),
        }
        for value in TEXT_ORIENTATIONS:
            self.title_orientation_input.addItem(orientation_labels[value], value)
        self.title_orientation_input.setCurrentIndex(
            max(0, self.title_orientation_input.findData(self.track.title_orientation))
        )
        self.title_position_input = QComboBox()
        position_labels = {
            "top": self._text("Ближе к верху", "Жоғарыға жақын", "Near top"),
            "center": self._text("По центру", "Ортада", "Centred"),
            "bottom": self._text("Ближе к низу", "Төменге жақын", "Near bottom"),
        }
        for value in TEXT_VERTICAL_POSITIONS:
            self.title_position_input.addItem(position_labels[value], value)
        self.title_position_input.setCurrentIndex(
            max(0, self.title_position_input.findData(self.track.title_position))
        )
        self.group_input = QLineEdit(self.track.group_title)
        self.group_input.setPlaceholderText(
            self._text("Например: Геология", "Мысалы: Геология", "For example: Geology")
        )
        self.width_input = QSpinBox()
        self.width_input.setRange(80, 2000)
        self.width_input.setSuffix(" px")
        self.width_input.setValue(self.track.width)
        self.axis_input = QLineEdit(self.track.x_axis_label)
        self.show_interval_labels_input = QCheckBox(
            self._text(
                "Показывать код/процент поверх рисунка",
                "Сурет үстінде кодты/пайызды көрсету",
                "Show code/percentage over pattern",
            )
        )
        self.show_interval_labels_input.setChecked(self.track.show_interval_labels)
        self.show_interval_labels_input.setEnabled(
            self.track.kind in {TrackKind.LITHOLOGY, TrackKind.CUTTINGS}
        )
        form.addRow(self._text("Название дорожки", "Жол атауы", "Track title"), self.title_input)
        form.addRow(
            self._text("Направление текста", "Мәтін бағыты", "Text direction"),
            self.title_orientation_input,
        )
        form.addRow(
            self._text("Положение текста", "Мәтін орны", "Text position"),
            self.title_position_input,
        )
        form.addRow(self._text("Название раздела", "Бөлім атауы", "Section title"), self.group_input)
        form.addRow(self._text("Ширина", "Ені", "Width"), self.width_input)
        form.addRow(self._text("Подпись оси X", "X осінің жазуы", "X-axis label"), self.axis_input)
        form.addRow(
            self._text("Подписи внутри интервалов", "Интервал ішіндегі жазулар", "Interval labels"),
            self.show_interval_labels_input,
        )
        form.addRow(self._text("Тип", "Түрі", "Type"), QLabel(self.track.kind.value))
        root.addLayout(form)

        root.addWidget(
            QLabel(
                self._text(
                    "Параметры внутри дорожки. Исходная мнемоника LAS не меняется; редактируется только подпись и оформление.",
                    "Жол ішіндегі параметрлер. Бастапқы LAS мнемоникасы өзгермейді; тек жазуы мен безендірілуі өңделеді.",
                    "Parameters inside the track. The source LAS mnemonic remains unchanged; only captions and presentation are edited.",
                )
            )
        )
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                self._text("LAS", "LAS", "LAS"),
                self._text("Подпись", "Жазу", "Caption"),
                self._text("Цвет", "Түс", "Colour"),
                self._text("Толщина", "Қалыңдық", "Width"),
                self._text("Стиль", "Стиль", "Style"),
                self._text("Шкала", "Шкала", "Scale"),
                self._text("Диапазон", "Диапазон", "Range"),
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._load_row)
        root.addWidget(self.table, 1)

        properties = QFormLayout()
        self.caption_input = QLineEdit()
        self.color_input = QLineEdit("#2563eb")
        color_row = QHBoxLayout()
        color_row.addWidget(self.color_input)
        color_button = QPushButton(self._text("Выбрать…", "Таңдау…", "Choose…"))
        color_button.clicked.connect(self._choose_color)
        color_row.addWidget(color_button)
        self.line_width_input = QDoubleSpinBox()
        self.line_width_input.setRange(0.5, 10.0)
        self.line_width_input.setSingleStep(0.25)
        self.line_width_input.setValue(1.5)
        self.style_input = QComboBox()
        for style in CurveLineStyle:
            self.style_input.addItem(self._style_name(style), style)
        self.scale_input = QComboBox()
        self.scale_input.addItem(self._text("Линейная", "Сызықтық", "Linear"), XScale.LINEAR)
        self.scale_input.addItem(
            self._text("Логарифмическая", "Логарифмдік", "Logarithmic"),
            XScale.LOGARITHMIC,
        )
        self.auto_range_input = QComboBox()
        self.auto_range_input.addItem(self._text("Авто", "Авто", "Automatic"), True)
        self.auto_range_input.addItem(self._text("Ручной", "Қолмен", "Manual"), False)
        self.auto_range_input.currentIndexChanged.connect(self._range_state)
        range_row = QHBoxLayout()
        self.min_input = QDoubleSpinBox()
        self.max_input = QDoubleSpinBox()
        for spin in (self.min_input, self.max_input):
            spin.setRange(-1e12, 1e12)
            spin.setDecimals(6)
        range_row.addWidget(self.min_input)
        range_row.addWidget(QLabel("…"))
        range_row.addWidget(self.max_input)
        properties.addRow(self._text("Подпись параметра", "Параметр жазуы", "Parameter caption"), self.caption_input)
        properties.addRow(self._text("Цвет", "Түс", "Colour"), color_row)
        properties.addRow(self._text("Толщина линии", "Сызық қалыңдығы", "Line width"), self.line_width_input)
        properties.addRow(self._text("Стиль линии", "Сызық стилі", "Line style"), self.style_input)
        properties.addRow(self._text("Шкала", "Шкала", "Scale"), self.scale_input)
        properties.addRow(self._text("Диапазон", "Диапазон", "Range mode"), self.auto_range_input)
        properties.addRow("", range_row)
        root.addLayout(properties)

        row_actions = QHBoxLayout()
        apply_row = QPushButton(self._text("Применить к параметру", "Параметрге қолдану", "Apply to parameter"))
        apply_row.clicked.connect(self._apply_row)
        row_actions.addWidget(apply_row)
        up = QPushButton("↑")
        down = QPushButton("↓")
        remove = QPushButton(self._text("Удалить из дорожки", "Жолдан жою", "Remove from track"))
        up.clicked.connect(lambda: self._move(-1))
        down.clicked.connect(lambda: self._move(1))
        remove.clicked.connect(self._remove)
        row_actions.addWidget(up)
        row_actions.addWidget(down)
        row_actions.addWidget(remove)
        row_actions.addStretch(1)
        root.addLayout(row_actions)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._reload()

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {"ru": ru, "kk": kk, "en": en}.get(self.language, ru)

    def _style_name(self, style: CurveLineStyle) -> str:
        return {
            CurveLineStyle.SOLID: self._text("Сплошная", "Тұтас", "Solid"),
            CurveLineStyle.DASH: self._text("Штриховая", "Үзік", "Dashed"),
            CurveLineStyle.DOT: self._text("Точечная", "Нүктелі", "Dotted"),
            CurveLineStyle.DASH_DOT: self._text("Штрих-точка", "Үзік-нүкте", "Dash-dot"),
        }[style]

    def _reload(self, selected: int | None = None) -> None:
        self._loading = True
        try:
            self.table.setRowCount(len(self.track.curve_mnemonics))
            for row, mnemonic in enumerate(self.track.curve_mnemonics):
                display = self.track.curve_display_settings(mnemonic)
                style = self.track.curve_style(mnemonic) or CurveStyle()
                range_text = (
                    self._text("Авто", "Авто", "Automatic")
                    if display.automatic_range
                    else f"{display.x_min:g} … {display.x_max:g}"
                )
                values = (
                    mnemonic,
                    display.display_name or mnemonic,
                    style.color,
                    f"{style.width:g}",
                    self._style_name(style.line_style),
                    display.x_scale.value,
                    range_text,
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(row, column, item)
            self.table.resizeColumnsToContents()
            if self.table.rowCount():
                row = min(selected if selected is not None else 0, self.table.rowCount() - 1)
                self.table.selectRow(row)
        finally:
            self._loading = False
        self._load_row()

    def _selected_row(self) -> int:
        return self.table.currentRow()

    def _load_row(self) -> None:
        if self._loading:
            return
        row = self._selected_row()
        if not 0 <= row < len(self.track.curve_mnemonics):
            self.caption_input.clear()
            return
        mnemonic = self.track.curve_mnemonics[row]
        display = self.track.curve_display_settings(mnemonic)
        style = self.track.curve_style(mnemonic) or CurveStyle()
        self.caption_input.setText(display.display_name or mnemonic)
        self.color_input.setText(style.color)
        self.line_width_input.setValue(style.width)
        self.style_input.setCurrentIndex(self.style_input.findData(style.line_style))
        self.scale_input.setCurrentIndex(self.scale_input.findData(display.x_scale))
        self.auto_range_input.setCurrentIndex(0 if display.automatic_range else 1)
        if not display.automatic_range:
            self.min_input.setValue(display.x_min or 0.0)
            self.max_input.setValue(display.x_max or 1.0)
        self._range_state()

    def _range_state(self) -> None:
        manual = self.auto_range_input.currentData() is False
        self.min_input.setEnabled(manual)
        self.max_input.setEnabled(manual)

    def _choose_color(self) -> None:
        initial = QColor(self.color_input.text())
        color = QColorDialog.getColor(initial if initial.isValid() else QColor("#2563eb"), self)
        if color.isValid():
            self.color_input.setText(color.name())

    def _apply_row(self) -> None:
        row = self._selected_row()
        if not 0 <= row < len(self.track.curve_mnemonics):
            return
        mnemonic = self.track.curve_mnemonics[row]
        caption = self.caption_input.text().strip()
        if not caption:
            QMessageBox.warning(self, self.windowTitle(), self._text("Подпись не должна быть пустой", "Жазу бос болмауы керек", "Caption cannot be empty"))
            return
        scale = self.scale_input.currentData()
        style_kind = self.style_input.currentData()
        if not isinstance(scale, XScale) or not isinstance(style_kind, CurveLineStyle):
            return
        manual = self.auto_range_input.currentData() is False
        minimum = self.min_input.value() if manual else None
        maximum = self.max_input.value() if manual else None
        try:
            display = CurveDisplaySettings(caption, scale, minimum, maximum)
            style = CurveStyle(self.color_input.text().strip(), self.line_width_input.value(), style_kind)
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.track.set_curve_display(mnemonic, display)
        self.track.set_curve_style(mnemonic, style)
        self._reload(row)

    def _move(self, offset: int) -> None:
        row = self._selected_row()
        target = row + offset
        if not 0 <= row < len(self.track.curve_mnemonics) or not 0 <= target < len(self.track.curve_mnemonics):
            return
        mnemonic = self.track.curve_mnemonics.pop(row)
        self.track.curve_mnemonics.insert(target, mnemonic)
        self._reload(target)

    def _remove(self) -> None:
        row = self._selected_row()
        if not 0 <= row < len(self.track.curve_mnemonics):
            return
        mnemonic = self.track.curve_mnemonics.pop(row)
        self.track.curve_styles.pop(mnemonic, None)
        self.track.curve_display.pop(mnemonic, None)
        self._reload(max(0, row - 1))

    def _accept(self) -> None:
        title = self.title_input.text().strip()
        group = self.group_input.text().strip()
        axis = self.axis_input.text().strip()
        if not title:
            QMessageBox.warning(self, self.windowTitle(), self._text("Название дорожки не должно быть пустым", "Жол атауы бос болмауы керек", "Track title cannot be empty"))
            return
        if len(title) > 120 or len(group) > 120 or len(axis) > 100:
            QMessageBox.warning(self, self.windowTitle(), self._text("Одна из подписей слишком длинная", "Жазулардың бірі тым ұзын", "One of the captions is too long"))
            return
        self.track.title = title
        self.track.title_orientation = str(
            self.title_orientation_input.currentData() or "horizontal"
        )
        self.track.title_position = str(
            self.title_position_input.currentData() or "center"
        )
        self.track.group_title = group
        self.track.show_interval_labels = self.show_interval_labels_input.isChecked()
        self.track.width = self.width_input.value()
        self.track.x_axis_label = axis
        try:
            self.track.__post_init__()
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.accept()
