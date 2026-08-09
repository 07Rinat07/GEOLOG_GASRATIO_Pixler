from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLabel, QSpinBox

from geoworkbench.tablet.vertical_ruler import (
    VerticalRulerMode,
    VerticalRulerTrackSettings,
)


class VerticalRulerSettingsWidget(QGroupBox):
    """Shared editor for one track's view of the tablet-wide vertical ruler."""

    settings_changed = Signal()

    def __init__(self, parent=None, *, language: str = "ru") -> None:
        super().__init__(parent)
        self.language = language
        self._loading = False
        self.setTitle(
            self._text(
                "Внутренняя вертикальная шкала",
                "Ішкі тік шкала",
                "Inner vertical ruler",
            )
        )

        form = QFormLayout(self)
        hint = QLabel(
            self._text(
                "Колонка использует общие значения глубины/времени и Y-координаты планшета. Здесь можно отключить внутреннюю шкалу или изменить частоту общих подписей и рисок.",
                "Баған планшеттің ортақ тереңдік/уақыт мәндері мен Y координаттарын қолданады. Мұнда ішкі шкаланы өшіруге немесе ортақ жазулар мен белгілердің жиілігін өзгертуге болады.",
                "The column uses the tablet-wide depth/time values and Y coordinates. Here you can hide the inner ruler or change the frequency of shared labels and ticks.",
            )
        )
        hint.setWordWrap(True)
        form.addRow(hint)

        self.mode_input = QComboBox()
        self.mode_input.addItem(
            self._text("Автоматически", "Автоматты", "Automatic"),
            VerticalRulerMode.AUTOMATIC.value,
        )
        self.mode_input.addItem(
            self._text("Цифры и риски", "Сандар мен белгілер", "Labels and ticks"),
            VerticalRulerMode.LABELS_AND_TICKS.value,
        )
        self.mode_input.addItem(
            self._text("Только риски", "Тек белгілер", "Ticks only"),
            VerticalRulerMode.TICKS_ONLY.value,
        )
        self.mode_input.addItem(
            self._text("Выключено", "Өшірулі", "Off"),
            VerticalRulerMode.OFF.value,
        )

        self.label_every_input = QSpinBox()
        self.major_tick_every_input = QSpinBox()
        self.minor_tick_every_input = QSpinBox()
        for control in (
            self.label_every_input,
            self.major_tick_every_input,
            self.minor_tick_every_input,
        ):
            control.setRange(1, 20)
            control.setSpecialValueText("1")

        form.addRow(self._text("Режим", "Режим", "Mode"), self.mode_input)
        form.addRow(
            self._text(
                "Подписывать каждую N-ю крупную отметку",
                "Әр N-ші ірі белгіні жазу",
                "Label every Nth major tick",
            ),
            self.label_every_input,
        )
        form.addRow(
            self._text(
                "Показывать каждую N-ю крупную риску",
                "Әр N-ші ірі сызықты көрсету",
                "Show every Nth major tick",
            ),
            self.major_tick_every_input,
        )
        form.addRow(
            self._text(
                "Показывать каждую N-ю мелкую риску",
                "Әр N-ші ұсақ сызықты көрсету",
                "Show every Nth minor tick",
            ),
            self.minor_tick_every_input,
        )

        self.mode_input.currentIndexChanged.connect(self._controls_changed)
        self.label_every_input.valueChanged.connect(self._controls_changed)
        self.major_tick_every_input.valueChanged.connect(self._controls_changed)
        self.minor_tick_every_input.valueChanged.connect(self._controls_changed)
        self.set_settings(VerticalRulerTrackSettings())

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {"ru": ru, "kk": kk, "en": en}.get(self.language, ru)

    def mode(self) -> VerticalRulerMode:
        try:
            return VerticalRulerMode(str(self.mode_input.currentData()))
        except ValueError:
            return VerticalRulerMode.AUTOMATIC

    def settings(self) -> VerticalRulerTrackSettings:
        return VerticalRulerTrackSettings(
            mode=self.mode(),
            label_every_major=self.label_every_input.value(),
            major_tick_every=self.major_tick_every_input.value(),
            minor_tick_every=self.minor_tick_every_input.value(),
        )

    def set_settings(
        self,
        settings: VerticalRulerTrackSettings,
        *,
        editable: bool = True,
    ) -> None:
        if not isinstance(settings, VerticalRulerTrackSettings):
            raise ValueError("Некорректные настройки внутренней вертикальной шкалы")
        self._loading = True
        try:
            index = self.mode_input.findData(settings.mode.value)
            self.mode_input.setCurrentIndex(index if index >= 0 else 0)
            self.label_every_input.setValue(settings.label_every_major)
            self.major_tick_every_input.setValue(settings.major_tick_every)
            self.minor_tick_every_input.setValue(settings.minor_tick_every)
            self.setEnabled(editable)
        finally:
            self._loading = False
        self.update_control_state()

    def update_control_state(self) -> None:
        enabled = self.isEnabled()
        mode = self.mode()
        self.label_every_input.setEnabled(
            enabled and mode not in {VerticalRulerMode.TICKS_ONLY, VerticalRulerMode.OFF}
        )
        ticks_enabled = enabled and mode is not VerticalRulerMode.OFF
        self.major_tick_every_input.setEnabled(ticks_enabled)
        self.minor_tick_every_input.setEnabled(ticks_enabled)

    def _controls_changed(self, *_args) -> None:
        self.update_control_state()
        if not self._loading:
            self.settings_changed.emit()
