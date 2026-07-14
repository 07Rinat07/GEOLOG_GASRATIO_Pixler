from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.tablet.models import TrackDefinition, XScale


class TrackInspector(QWidget):
    settings_requested = Signal(str, int, str, object, object)

    def __init__(self) -> None:
        super().__init__()
        self._track_id: str | None = None
        self._stack = QStackedWidget()

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._stack.addWidget(self._text)

        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        self._summary = QLabel()
        self._summary.setWordWrap(True)
        editor_layout.addWidget(self._summary)

        form = QFormLayout()
        self.width_input = QSpinBox()
        self.width_input.setRange(80, 2000)
        form.addRow("Ширина, px", self.width_input)

        self.scale_input = QComboBox()
        self.scale_input.addItem("Линейная", XScale.LINEAR.value)
        self.scale_input.addItem("Логарифмическая", XScale.LOGARITHMIC.value)
        form.addRow("Шкала X", self.scale_input)

        self.auto_range_input = QCheckBox("Автоматически")
        self.auto_range_input.toggled.connect(self._update_range_enabled)
        form.addRow("Диапазон X", self.auto_range_input)

        self.minimum_input = self._range_spin_box()
        self.maximum_input = self._range_spin_box()
        form.addRow("Минимум X", self.minimum_input)
        form.addRow("Максимум X", self.maximum_input)
        editor_layout.addLayout(form)

        self.apply_button = QPushButton("Применить")
        self.apply_button.clicked.connect(self._emit_settings)
        editor_layout.addWidget(self.apply_button)
        editor_layout.addStretch(1)
        self._stack.addWidget(editor)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)
        self.setPlainText("Свойства выбранного набора, кривой или трека")

    def setPlainText(self, text: str) -> None:  # noqa: N802
        self._track_id = None
        self._text.setPlainText(text)
        self._stack.setCurrentIndex(0)

    def show_track(self, track: TrackDefinition) -> None:
        self._track_id = track.track_id
        self._summary.setText(
            f"{track.title}\n"
            f"Тип: {track.kind.value}\n"
            f"Кривые: {', '.join(track.curve_mnemonics) or 'нет'}"
        )
        self.width_input.setValue(track.width)
        self.scale_input.setCurrentIndex(
            self.scale_input.findData(track.x_scale.value)
        )
        automatic = track.x_min is None or track.x_max is None
        self.auto_range_input.setChecked(automatic)
        self.minimum_input.setValue(track.x_min if track.x_min is not None else 0.1)
        self.maximum_input.setValue(track.x_max if track.x_max is not None else 100.0)
        self._update_range_enabled(automatic)
        self._stack.setCurrentIndex(1)

    @staticmethod
    def _range_spin_box() -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-1e12, 1e12)
        spin.setDecimals(6)
        return spin

    def _update_range_enabled(self, automatic: bool) -> None:
        self.minimum_input.setEnabled(not automatic)
        self.maximum_input.setEnabled(not automatic)

    def _emit_settings(self) -> None:
        if self._track_id is None:
            return
        minimum: float | None = None
        maximum: float | None = None
        if not self.auto_range_input.isChecked():
            minimum = self.minimum_input.value()
            maximum = self.maximum_input.value()
        self.settings_requested.emit(
            self._track_id,
            self.width_input.value(),
            str(self.scale_input.currentData()),
            minimum,
            maximum,
        )
