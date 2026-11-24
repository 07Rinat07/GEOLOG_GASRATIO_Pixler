from __future__ import annotations

from geoworkbench.ui.stored_precision_spin_box import StoredPrecisionSpinBox


class CalcimetryPercentInput(StoredPrecisionSpinBox):
    """Edit an optional percentage while retaining the precision of a saved measurement."""

    def __init__(self, stored_percentage: float | None) -> None:
        super().__init__()
        self.setRange(-1.0, 100.0)
        self.setDecimals(1)
        self.setSpecialValueText("—")
        self.setSuffix(" %")
        if stored_percentage is None:
            self.setValue(-1.0)
        else:
            self.load_stored_value(stored_percentage)

    def percentage(self) -> float | None:
        percentage = self.effective_value()
        return percentage if percentage >= 0 else None
