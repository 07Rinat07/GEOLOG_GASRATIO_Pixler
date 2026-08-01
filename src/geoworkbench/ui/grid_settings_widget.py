from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from geoworkbench.tablet.grid_geometry import (
    DEFAULT_GRID_ALPHA,
    DEFAULT_GRID_MAJOR_DIVISIONS,
    DEFAULT_GRID_MINOR_DIVISIONS,
)


class GridSettingsWidget(QWidget):
    """Shared, explicit editor for one track's screen and print grid.

    The horizontal depth/time grid follows the application-wide five-unit
    standard.  Major/minor division controls therefore apply only to the
    parameter (X) axis, which is made explicit in both labels and help text.
    """

    settings_changed = Signal()

    def __init__(self, parent=None, *, language: str | Enum = "ru") -> None:
        super().__init__(parent)
        self.language = self._language_code(language)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self._form = QFormLayout()
        self.grid_x_input = QCheckBox()
        self.grid_y_input = QCheckBox()
        self.grid_major_input = QSpinBox()
        self.grid_major_input.setRange(1, 20)
        self.grid_minor_input = QSpinBox()
        self.grid_minor_input.setRange(1, 20)
        self.grid_alpha_input = QDoubleSpinBox()
        self.grid_alpha_input.setRange(0.0, 1.0)
        self.grid_alpha_input.setSingleStep(0.05)
        self.grid_alpha_input.setDecimals(2)
        self.grid_print_input = QCheckBox()
        self.grid_major_label = QLabel()
        self.grid_minor_label = QLabel()
        self.grid_alpha_label = QLabel()

        self._form.addRow(self.grid_x_input)
        self._form.addRow(self.grid_y_input)
        self._form.addRow(self.grid_major_label, self.grid_major_input)
        self._form.addRow(self.grid_minor_label, self.grid_minor_input)
        self._form.addRow(self.grid_alpha_label, self.grid_alpha_input)
        self._form.addRow(self.grid_print_input)
        root.addLayout(self._form)

        self.depth_standard_hint = QLabel()
        self.depth_standard_hint.setWordWrap(True)
        self.depth_standard_hint.setStyleSheet(
            "padding:5px 7px; border:1px solid #cbd5e1; border-radius:4px; "
            "background:#f8fafc; color:#475569;"
        )
        root.addWidget(self.depth_standard_hint)

        self.standard_button = QPushButton()
        root.addWidget(self.standard_button)

        self.grid_x_input.toggled.connect(self._grid_visibility_changed)
        self.grid_y_input.toggled.connect(self._grid_visibility_changed)
        self.grid_major_input.valueChanged.connect(self._emit_changed)
        self.grid_minor_input.valueChanged.connect(self._emit_changed)
        self.grid_alpha_input.valueChanged.connect(self._emit_changed)
        self.grid_print_input.toggled.connect(self._emit_changed)
        self.standard_button.clicked.connect(self.apply_standard)

        self.set_language(language)
        self.set_values(True, True, 5, 5, 0.2, True)

    @staticmethod
    def _language_code(language: str | Enum) -> str:
        value = getattr(language, "value", language)
        return str(value) if str(value) in {"ru", "kk", "en"} else "ru"

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {"ru": ru, "kk": kk, "en": en}.get(self.language, ru)

    def set_language(self, language: str | Enum) -> None:
        self.language = self._language_code(language)
        self.grid_x_input.setText(
            self._text(
                "Сетка параметра X (вертикальные линии)",
                "X параметр торы (тік сызықтар)",
                "Parameter X grid (vertical lines)",
            )
        )
        self.grid_y_input.setText(
            self._text(
                "Сетка глубины/времени (горизонтальные линии)",
                "Тереңдік/уақыт торы (көлденең сызықтар)",
                "Depth/time grid (horizontal lines)",
            )
        )
        self.grid_print_input.setText(
            self._text(
                "Печатать сетку этой колонки",
                "Осы бағанның торын басып шығару",
                "Print this column's grid",
            )
        )
        self.grid_major_label.setText(
            self._text(
                "Основных интервалов по X",
                "X бойынша негізгі аралықтар",
                "Major intervals on X",
            )
        )
        self.grid_minor_label.setText(
            self._text(
                "Делений внутри интервала X",
                "X аралығындағы бөліністер",
                "Subdivisions per X interval",
            )
        )
        self.grid_alpha_label.setText(
            self._text(
                "Интенсивность сетки (0–1)",
                "Тор қарқындылығы (0–1)",
                "Grid intensity (0–1)",
            )
        )
        self.depth_standard_hint.setText(
            self._text(
                "Сетка вертикальной оси общая для всей формы. Для глубины: шаг "
                "5 единиц и круглые значения (50, 55, 60…); для времени шаг "
                "подбирается адаптивно. "
                "Поля делений выше относятся только к оси X.",
                "Тік ось торы бүкіл пішінге ортақ. Тереңдік үшін қадам 5 бірлік "
                "және дөңгелек мәндер (50, 55, 60…); уақыт үшін қадам бейімделіп "
                "таңдалады. "
                "Жоғарыдағы бөліністер тек X осіне қатысты.",
                "The vertical-axis grid is shared by the whole form. Depth uses "
                "a 5-unit step aligned to round values (50, 55, 60…); time uses "
                "an adaptive step. "
                "The division fields above apply only to the X axis.",
            )
        )
        self.standard_button.setText(
            self._text("Стандарт 5×5", "5×5 стандарты", "5×5 standard")
        )
        self._update_accessibility()

    def _update_accessibility(self) -> None:
        controls = (
            (
                self.grid_x_input,
                self.grid_x_input.text(),
                self._text(
                    "Включает вертикальную сетку шкалы параметра.",
                    "Параметр шкаласының тік торын қосады.",
                    "Shows the vertical grid for the parameter scale.",
                ),
            ),
            (
                self.grid_y_input,
                self.grid_y_input.text(),
                self._text(
                    "Включает общую горизонтальную сетку: глубина через 5 единиц, время адаптивно.",
                    "Ортақ көлденең торды қосады: тереңдік 5 бірлікте, уақыт бейімделеді.",
                    "Shows the shared horizontal grid: depth every 5 units, time adaptively.",
                ),
            ),
            (
                self.grid_major_input,
                self._text(
                    "Основные интервалы сетки X",
                    "X торының негізгі аралықтары",
                    "X grid major intervals",
                ),
                self._text(
                    "Количество основных интервалов только по оси X.",
                    "Тек X осіндегі негізгі аралықтар саны.",
                    "Number of major intervals on the X axis only.",
                ),
            ),
            (
                self.grid_minor_input,
                self._text(
                    "Малые деления сетки X",
                    "X торының кіші бөліністері",
                    "X grid subdivisions",
                ),
                self._text(
                    "Количество малых делений внутри каждого основного интервала X.",
                    "Әрбір негізгі X аралығындағы кіші бөліністер саны.",
                    "Number of subdivisions inside each major X interval.",
                ),
            ),
            (
                self.grid_alpha_input,
                self._text(
                    "Интенсивность сетки",
                    "Тор қарқындылығы",
                    "Grid intensity",
                ),
                self._text(
                    "0 — невидимая сетка, 1 — полностью непрозрачная.",
                    "0 — көрінбейді, 1 — толық мөлдір емес.",
                    "0 is invisible; 1 is fully opaque.",
                ),
            ),
            (
                self.grid_print_input,
                self.grid_print_input.text(),
                self._text(
                    "Если выключено, сетка остаётся на экране, но не выводится при печати.",
                    "Өшірілсе, тор экранда қалады, бірақ басып шығарылмайды.",
                    "When off, the grid remains on screen but is omitted from print.",
                ),
            ),
            (
                self.standard_button,
                self.standard_button.text(),
                self._text(
                    "Включить X и Y, установить 5 основных × 5 малых делений, "
                    "прозрачность 0,20 и печать сетки.",
                    "X және Y қосып, 5 негізгі × 5 кіші бөлініс, 0,20 мөлдірлік "
                    "және торды басып шығаруды орнату.",
                    "Enable X and Y, set 5 major × 5 minor divisions, 0.20 opacity, "
                    "and print the grid.",
                ),
            ),
        )
        for control, accessible_name, tooltip in controls:
            control.setAccessibleName(accessible_name)
            control.setToolTip(tooltip)
        self.depth_standard_hint.setAccessibleName(
            self._text(
                "Стандарт сетки глубины и времени",
                "Тереңдік және уақыт торының стандарты",
                "Depth and time grid standard",
            )
        )
        self.depth_standard_hint.setToolTip(self.depth_standard_hint.text())

    def set_values(
        self,
        grid_x: bool,
        grid_y: bool,
        major_divisions: int,
        minor_divisions: int,
        alpha: float,
        print_grid: bool,
    ) -> None:
        values: tuple[tuple[QWidget, bool | int | float], ...] = (
            (self.grid_x_input, bool(grid_x)),
            (self.grid_y_input, bool(grid_y)),
            (self.grid_major_input, int(major_divisions)),
            (self.grid_minor_input, int(minor_divisions)),
            (self.grid_alpha_input, float(alpha)),
            (self.grid_print_input, bool(print_grid)),
        )
        previous = [
            input_widget.blockSignals(True) for input_widget, _value in values
        ]
        try:
            for input_widget, value in values:
                if isinstance(input_widget, QCheckBox):
                    input_widget.setChecked(bool(value))
                elif isinstance(input_widget, QSpinBox):
                    input_widget.setValue(int(value))
                elif isinstance(input_widget, QDoubleSpinBox):
                    input_widget.setValue(float(value))
                else:
                    raise TypeError("Неподдерживаемый элемент настройки сетки")
        finally:
            for (input_widget, _value), was_blocked in zip(
                values, previous, strict=True
            ):
                input_widget.blockSignals(was_blocked)
        self._update_dependent_states()

    def values(self) -> tuple[bool, bool, int, int, float, bool]:
        return (
            self.grid_x_input.isChecked(),
            self.grid_y_input.isChecked(),
            self.grid_major_input.value(),
            self.grid_minor_input.value(),
            self.grid_alpha_input.value(),
            self.grid_print_input.isChecked(),
        )

    def apply_standard(self) -> None:
        self.set_values(
            True,
            True,
            DEFAULT_GRID_MAJOR_DIVISIONS,
            DEFAULT_GRID_MINOR_DIVISIONS,
            DEFAULT_GRID_ALPHA,
            True,
        )
        self.settings_changed.emit()

    def _grid_visibility_changed(self, _checked: bool) -> None:
        self._update_dependent_states()
        self.settings_changed.emit()

    def _emit_changed(self, _value=None) -> None:
        self.settings_changed.emit()

    def _update_dependent_states(self) -> None:
        has_x_grid = self.grid_x_input.isChecked()
        has_any_grid = has_x_grid or self.grid_y_input.isChecked()
        self.grid_major_label.setEnabled(has_x_grid)
        self.grid_major_input.setEnabled(has_x_grid)
        self.grid_minor_label.setEnabled(has_x_grid)
        self.grid_minor_input.setEnabled(has_x_grid)
        self.grid_alpha_label.setEnabled(has_any_grid)
        self.grid_alpha_input.setEnabled(has_any_grid)
        self.grid_print_input.setEnabled(has_any_grid)
