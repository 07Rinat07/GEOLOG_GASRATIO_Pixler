from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox


class StoredPrecisionSpinBox(QDoubleSpinBox):
    """Keep a saved number while its rounded value on screen stays the same."""

    def __init__(self) -> None:
        super().__init__()
        self._stored_value: float | None = None
        self._stored_display: float | None = None

    def load_stored_value(self, value: float) -> None:
        self.setValue(value)
        self._stored_value = value
        self._stored_display = self.value()

    def effective_value(self) -> float:
        displayed = self.value()
        if self._stored_value is not None and displayed == self._stored_display:
            return self._stored_value
        return displayed


def cuttings_depth_input(depth: float, stored_depth: float | None = None) -> StoredPrecisionSpinBox:
    control = StoredPrecisionSpinBox()
    control.setRange(-100_000.0, 100_000.0)
    control.setDecimals(3)
    control.setSuffix(" m")
    if stored_depth is None:
        control.setValue(float(depth))
    else:
        control.load_stored_value(float(stored_depth))
    return control
