from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from geoworkbench.domain.models import Dataset


class CurveView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._plot = pg.PlotWidget()
        self._plot.showGrid(x=True, y=True, alpha=0.25)
        self._plot.setLabel("left", "Глубина", units="м")
        self._plot.setLabel("bottom", "Значение")
        self._title = QLabel("Откройте LAS-файл")
        self._title.setStyleSheet("font-weight: 600; padding: 6px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._title)
        layout.addWidget(self._plot)

    def clear(self) -> None:
        self._plot.clear()
        self._title.setText("Откройте LAS-файл")

    def show_dataset(self, dataset: Dataset, selected: list[str] | None = None) -> None:
        self._plot.clear()
        selected_names = selected or [
            curve.metadata.original_mnemonic for curve in list(dataset.curves.values())[:6]
        ]
        count = 0
        for curve in dataset.curves.values():
            mnemonic = curve.metadata.original_mnemonic
            if mnemonic not in selected_names:
                continue
            values = np.asarray(curve.values, dtype=float)
            valid = np.isfinite(values) & np.isfinite(dataset.depth)
            if not np.any(valid):
                continue
            self._plot.plot(values[valid], dataset.depth[valid], name=mnemonic)
            count += 1
        self._plot.getViewBox().invertY(True)
        self._title.setText(f"{dataset.name}: показано кривых — {count}, отсчётов — {len(dataset.depth)}")
