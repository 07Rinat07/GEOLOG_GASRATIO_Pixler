from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox


class CalcimetryPercentInput(QDoubleSpinBox):
    """Edit an optional percentage while retaining the precision of a saved measurement."""

    def __init__(self, stored_percentage: float | None) -> None:
        super().__init__()
        self.setRange(-1.0, 100.0)
        self.setDecimals(1)
        self.setSpecialValueText("—")
        self.setSuffix(" %")
        self.setValue(stored_percentage if stored_percentage is not None else -1.0)
        self._stored_percentage = stored_percentage
        self._initial_displayed_value = self.value()

    def percentage(self) -> float | None:
        displayed = self.value()
        # The spin box rounds on load. Only a different number replaces the saved value.
        percentage = (
            self._stored_percentage if displayed == self._initial_displayed_value else displayed
        )
        return percentage if percentage is not None and percentage >= 0 else None
