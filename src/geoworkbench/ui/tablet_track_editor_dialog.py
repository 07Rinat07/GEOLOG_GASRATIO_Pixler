from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
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
    minimum_track_width,
)
from geoworkbench.ui.adaptive_toolbar import AdaptiveActionToolBar
from geoworkbench.ui.tablet_track_preview_widget import TabletTrackPreviewWidget


class TabletTrackEditorDialog(QDialog):
    """Adaptive editor with immediate visual control of a tablet track."""

    SETTINGS_KEY = "ui/tablet_track_editor/splitter"

    def __init__(self, track: TrackDefinition, parent=None, *, language: str = "ru") -> None:
        super().__init__(parent)
        self.language = language
        self.track = deepcopy(track)
        self._loading = False
        self.setWindowTitle(
            self._text("Редактор колонки/дорожки", "Баған/жол редакторы", "Column/track editor")
        )
        self.setMinimumSize(900, 620)
        self.resize(1480, 860)

        root = QVBoxLayout(self)
        self.toolbar = AdaptiveActionToolBar(parent=self)
        self.apply_action = self.toolbar.add_standard_action(
            self._text("Применить параметр", "Параметрді қолдану", "Apply parameter"),
            self._apply_row,
            icon=QStyle.StandardPixmap.SP_DialogApplyButton,
        )
        self.toolbar.addSeparator()
        self.toolbar.add_standard_action(
            self._text("Выше", "Жоғары", "Move up"),
            lambda: self._move(-1),
            icon=QStyle.StandardPixmap.SP_ArrowUp,
        )
        self.toolbar.add_standard_action(
            self._text("Ниже", "Төмен", "Move down"),
            lambda: self._move(1),
            icon=QStyle.StandardPixmap.SP_ArrowDown,
        )
        self.toolbar.add_standard_action(
            self._text("Удалить", "Жою", "Remove"),
            self._remove,
            icon=QStyle.StandardPixmap.SP_TrashIcon,
        )
        self.toolbar.add_stretch()
        root.addWidget(self.toolbar)

        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(4, 4, 4, 4)

        track_group = QGroupBox(
            self._text("Заголовок и геометрия", "Тақырып және геометрия", "Header and geometry")
        )
        form = QFormLayout(track_group)
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
        self.width_input.setRange(minimum_track_width(self.track.kind), 2000)
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
        editor_layout.addWidget(track_group)

        grid_group = QGroupBox(self._text("Сетка", "Тор", "Grid"))
        grid_form = QFormLayout(grid_group)
        self.grid_x_input = QCheckBox(
            self._text("Вертикальные линии", "Тік сызықтар", "Vertical lines")
        )
        self.grid_x_input.setChecked(self.track.grid_x)
        self.grid_y_input = QCheckBox(
            self._text("Горизонтальные линии", "Көлденең сызықтар", "Horizontal lines")
        )
        self.grid_y_input.setChecked(self.track.grid_y)
        visibility = QHBoxLayout()
        visibility.addWidget(self.grid_x_input)
        visibility.addWidget(self.grid_y_input)
        visibility.addStretch(1)
        self.grid_major_input = QSpinBox()
        self.grid_major_input.setRange(1, 20)
        self.grid_major_input.setValue(self.track.grid_major_divisions)
        self.grid_minor_input = QSpinBox()
        self.grid_minor_input.setRange(1, 20)
        self.grid_minor_input.setValue(self.track.grid_minor_divisions)
        divisions = QHBoxLayout()
        divisions.addWidget(self.grid_major_input)
        divisions.addWidget(QLabel(self._text("основных", "негізгі", "major")))
        divisions.addWidget(self.grid_minor_input)
        divisions.addWidget(QLabel(self._text("малых", "ұсақ", "minor")))
        divisions.addStretch(1)
        self.grid_alpha_input = QDoubleSpinBox()
        self.grid_alpha_input.setRange(0.0, 1.0)
        self.grid_alpha_input.setSingleStep(0.05)
        self.grid_alpha_input.setDecimals(2)
        self.grid_alpha_input.setValue(self.track.grid_alpha)
        self.grid_print_input = QCheckBox(
            self._text("Печатать сетку", "Торды басып шығару", "Print grid")
        )
        self.grid_print_input.setChecked(self.track.grid_print)
        grid_form.addRow(self._text("Линии", "Сызықтар", "Lines"), visibility)
        grid_form.addRow(self._text("Деления", "Бөліністер", "Divisions"), divisions)
        grid_form.addRow(self._text("Прозрачность", "Мөлдірлік", "Opacity"), self.grid_alpha_input)
        grid_form.addRow("", self.grid_print_input)
        editor_layout.addWidget(grid_group)

        curves_group = QGroupBox(
            self._text("Параметры и шапки кривых", "Параметрлер және қисық тақырыптары", "Curve parameters and headers")
        )
        curves_layout = QVBoxLayout(curves_group)
        hint = QLabel(
            self._text(
                "Выберите параметр. Все изменения справа сразу видны в предпросмотре; кнопка «Применить параметр» фиксирует их в редактируемой дорожке.",
                "Параметрді таңдаңыз. Өзгерістер алдын ала қарауда бірден көрінеді.",
                "Select a parameter. Changes are reflected immediately in the preview; Apply parameter commits them to the edited track.",
            )
        )
        hint.setWordWrap(True)
        curves_layout.addWidget(hint)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "LAS",
                self._text("Подпись", "Жазу", "Caption"),
                self._text("Цвет", "Түс", "Colour"),
                self._text("Толщина", "Қалыңдық", "Width"),
                self._text("Стиль", "Стиль", "Style"),
                self._text("Шкала", "Шкала", "Scale"),
                self._text("Диапазон", "Диапазон", "Range"),
                self._text("Текст шапки", "Тақырып мәтіні", "Header text"),
                self._text("Линия шапки", "Тақырып сызығы", "Header line"),
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._load_row)
        self.table.setMinimumHeight(190)
        curves_layout.addWidget(self.table)

        properties = QFormLayout()
        self.caption_input = QLineEdit()
        self.color_input = QLineEdit("#2563eb")
        color_row = self._color_row(self.color_input, "#2563eb")
        self.header_text_color_input = QLineEdit("#0f172a")
        header_text_color_row = self._color_row(self.header_text_color_input, "#0f172a")
        self.header_line_color_input = QLineEdit()
        self.header_line_color_input.setPlaceholderText(
            self._text("Как цвет кривой", "Қисық түсі сияқты", "Same as curve")
        )
        header_line_color_row = QHBoxLayout()
        header_line_color_row.addWidget(self.header_line_color_input)
        choose_line = QPushButton(self._text("Выбрать…", "Таңдау…", "Choose…"))
        choose_line.clicked.connect(
            lambda: self._choose_color_for(
                self.header_line_color_input, self.color_input.text() or "#2563eb"
            )
        )
        clear_line = QPushButton(self._text("Как кривая", "Қисық сияқты", "Use curve"))
        clear_line.clicked.connect(self.header_line_color_input.clear)
        header_line_color_row.addWidget(choose_line)
        header_line_color_row.addWidget(clear_line)
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
        properties.addRow(self._text("Цвет кривой", "Қисық түсі", "Curve colour"), color_row)
        properties.addRow(self._text("Цвет названия", "Атау түсі", "Header text colour"), header_text_color_row)
        properties.addRow(self._text("Линия под названием", "Атау астындағы сызық", "Header underline"), header_line_color_row)
        properties.addRow(self._text("Толщина линии", "Сызық қалыңдығы", "Line width"), self.line_width_input)
        properties.addRow(self._text("Стиль линии", "Сызық стилі", "Line style"), self.style_input)
        properties.addRow(self._text("Шкала", "Шкала", "Scale"), self.scale_input)
        properties.addRow(self._text("Диапазон", "Диапазон", "Range mode"), self.auto_range_input)
        properties.addRow("", range_row)
        curves_layout.addLayout(properties)
        editor_layout.addWidget(curves_group)
        editor_layout.addStretch(1)

        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setWidget(editor_widget)
        editor_scroll.setMinimumWidth(480)

        preview_group = QGroupBox(
            self._text("Живой предпросмотр печати", "Баспаға тірі алдын ала қарау", "Live print preview")
        )
        preview_layout = QVBoxLayout(preview_group)
        preview_hint = QLabel(
            self._text(
                "Предпросмотр использует текущие значения полей ещё до нажатия ОК.",
                "Алдын ала қарау ОК басылғанға дейін ағымдағы мәндерді қолданады.",
                "The preview uses current control values before OK is pressed.",
            )
        )
        preview_hint.setWordWrap(True)
        preview_layout.addWidget(preview_hint)
        self.preview = TabletTrackPreviewWidget(self.track, preview_group)
        preview_layout.addWidget(self.preview, 1)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(editor_scroll)
        self.splitter.addWidget(preview_group)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        saved_state = QSettings().value(self.SETTINGS_KEY)
        if saved_state is not None:
            self.splitter.restoreState(saved_state)
        else:
            self.splitter.setSizes([760, 680])
        root.addWidget(self.splitter, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._connect_preview_signals()
        self._reload()
        self._refresh_preview()

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {"ru": ru, "kk": kk, "en": en}.get(self.language, ru)

    def _style_name(self, style: CurveLineStyle) -> str:
        return {
            CurveLineStyle.SOLID: self._text("Сплошная", "Тұтас", "Solid"),
            CurveLineStyle.DASH: self._text("Штриховая", "Үзік", "Dashed"),
            CurveLineStyle.DOT: self._text("Точечная", "Нүктелі", "Dotted"),
            CurveLineStyle.DASH_DOT: self._text("Штрих-точка", "Үзік-нүкте", "Dash-dot"),
        }[style]

    def _color_row(self, target: QLineEdit, fallback: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(target)
        button = QPushButton(self._text("Выбрать…", "Таңдау…", "Choose…"))
        button.clicked.connect(lambda: self._choose_color_for(target, fallback))
        row.addWidget(button)
        return row

    def _connect_preview_signals(self) -> None:
        for control in (
            self.title_input,
            self.group_input,
            self.axis_input,
            self.caption_input,
            self.color_input,
            self.header_text_color_input,
            self.header_line_color_input,
        ):
            control.textChanged.connect(self._refresh_preview)
        for control in (
            self.title_orientation_input,
            self.title_position_input,
            self.style_input,
            self.scale_input,
            self.auto_range_input,
        ):
            control.currentIndexChanged.connect(self._refresh_preview)
        for control in (
            self.width_input,
            self.grid_major_input,
            self.grid_minor_input,
            self.grid_alpha_input,
            self.line_width_input,
            self.min_input,
            self.max_input,
        ):
            control.valueChanged.connect(self._refresh_preview)
        for control in (
            self.show_interval_labels_input,
            self.grid_x_input,
            self.grid_y_input,
            self.grid_print_input,
        ):
            control.toggled.connect(self._refresh_preview)

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
                    display.header_text_color,
                    display.header_line_color or style.color,
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
            self._refresh_preview()
            return
        mnemonic = self.track.curve_mnemonics[row]
        display = self.track.curve_display_settings(mnemonic)
        style = self.track.curve_style(mnemonic) or CurveStyle()
        controls = (
            self.caption_input,
            self.color_input,
            self.header_text_color_input,
            self.header_line_color_input,
            self.line_width_input,
            self.style_input,
            self.scale_input,
            self.auto_range_input,
            self.min_input,
            self.max_input,
        )
        for control in controls:
            control.blockSignals(True)
        try:
            self.caption_input.setText(display.display_name or mnemonic)
            self.color_input.setText(style.color)
            self.header_text_color_input.setText(display.header_text_color)
            self.header_line_color_input.setText(display.header_line_color or "")
            self.line_width_input.setValue(style.width)
            self.style_input.setCurrentIndex(self.style_input.findData(style.line_style))
            self.scale_input.setCurrentIndex(self.scale_input.findData(display.x_scale))
            self.auto_range_input.setCurrentIndex(0 if display.automatic_range else 1)
            if not display.automatic_range:
                self.min_input.setValue(display.x_min or 0.0)
                self.max_input.setValue(display.x_max or 1.0)
        finally:
            for control in controls:
                control.blockSignals(False)
        self._range_state()
        self._refresh_preview()

    def _range_state(self) -> None:
        manual = self.auto_range_input.currentData() is False
        self.min_input.setEnabled(manual)
        self.max_input.setEnabled(manual)
        self._refresh_preview()

    def _choose_color_for(self, target: QLineEdit, fallback: str) -> None:
        initial = QColor(target.text())
        color = QColorDialog.getColor(
            initial if initial.isValid() else QColor(fallback), self
        )
        if color.isValid():
            target.setText(color.name())

    def _apply_parameter_controls(self, target: TrackDefinition) -> None:
        row = self._selected_row()
        if not 0 <= row < len(target.curve_mnemonics):
            return
        mnemonic = target.curve_mnemonics[row]
        caption = self.caption_input.text().strip() or mnemonic
        scale = self.scale_input.currentData()
        style_kind = self.style_input.currentData()
        if not isinstance(scale, XScale) or not isinstance(style_kind, CurveLineStyle):
            return
        manual = self.auto_range_input.currentData() is False
        current_display = target.curve_display_settings(mnemonic)
        display = CurveDisplaySettings(
            display_name=caption,
            x_scale=scale,
            x_min=self.min_input.value() if manual else None,
            x_max=self.max_input.value() if manual else None,
            unit_override=current_display.unit_override,
            header_text_color=self.header_text_color_input.text().strip() or "#0f172a",
            header_line_color=(self.header_line_color_input.text().strip() or None),
        )
        style = CurveStyle(
            self.color_input.text().strip() or "#2563eb",
            self.line_width_input.value(),
            style_kind,
        )
        target.set_curve_display(mnemonic, display)
        target.set_curve_style(mnemonic, style)

    def _track_from_controls(self) -> TrackDefinition:
        candidate = deepcopy(self.track)
        candidate.title = self.title_input.text().strip() or self.track.title
        candidate.title_orientation = str(
            self.title_orientation_input.currentData() or "horizontal"
        )
        candidate.title_position = str(self.title_position_input.currentData() or "center")
        candidate.group_title = self.group_input.text().strip()
        candidate.width = self.width_input.value()
        candidate.x_axis_label = self.axis_input.text().strip()
        candidate.show_interval_labels = self.show_interval_labels_input.isChecked()
        candidate.grid_x = self.grid_x_input.isChecked()
        candidate.grid_y = self.grid_y_input.isChecked()
        candidate.grid_major_divisions = self.grid_major_input.value()
        candidate.grid_minor_divisions = self.grid_minor_input.value()
        candidate.grid_alpha = self.grid_alpha_input.value()
        candidate.grid_print = self.grid_print_input.isChecked()
        try:
            self._apply_parameter_controls(candidate)
            candidate.__post_init__()
        except ValueError:
            return deepcopy(self.track)
        return candidate

    def _refresh_preview(self, *_args) -> None:
        if self._loading:
            return
        self.preview.set_track(self._track_from_controls())

    def _apply_row(self) -> None:
        row = self._selected_row()
        if not 0 <= row < len(self.track.curve_mnemonics):
            return
        if not self.caption_input.text().strip():
            QMessageBox.warning(
                self,
                self.windowTitle(),
                self._text(
                    "Подпись не должна быть пустой",
                    "Жазу бос болмауы керек",
                    "Caption cannot be empty",
                ),
            )
            return
        try:
            self._apply_parameter_controls(self.track)
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self._reload(row)

    def _move(self, offset: int) -> None:
        row = self._selected_row()
        target = row + offset
        if not 0 <= row < len(self.track.curve_mnemonics) or not 0 <= target < len(
            self.track.curve_mnemonics
        ):
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
            QMessageBox.warning(
                self,
                self.windowTitle(),
                self._text(
                    "Название дорожки не должно быть пустым",
                    "Жол атауы бос болмауы керек",
                    "Track title cannot be empty",
                ),
            )
            return
        if len(title) > 120 or len(group) > 120 or len(axis) > 100:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                self._text(
                    "Одна из подписей слишком длинная",
                    "Жазулардың бірі тым ұзын",
                    "One of the captions is too long",
                ),
            )
            return
        try:
            self._apply_parameter_controls(self.track)
            candidate = self._track_from_controls()
            candidate.__post_init__()
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.track = candidate
        QSettings().setValue(self.SETTINGS_KEY, self.splitter.saveState())
        self.accept()

    def reject(self) -> None:
        QSettings().setValue(self.SETTINGS_KEY, self.splitter.saveState())
        super().reject()
