from __future__ import annotations

from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype
from geoworkbench.services.localization import AppLanguage, Localizer


class LithologyIntervalDialog(QDialog):
    """Small editor opened after Shift+left drag in a lithology track.

    A lithology interval intentionally contains exactly one rock type.  Free-form
    descriptions and multi-component percentages belong to the cuttings sample
    editor and therefore are not exposed here.
    """

    def __init__(
        self,
        top_depth: float,
        bottom_depth: float,
        catalog: tuple[CatalogLithotype, ...],
        *,
        language: AppLanguage = AppLanguage.RU,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.localizer = Localizer.create(language)
        self.catalog = tuple(catalog)
        self.setWindowTitle(self._t("lithology.quick_title"))
        self.setModal(True)
        self.resize(460, 210)

        root = QVBoxLayout(self)
        hint = QLabel(self._t("lithology.quick_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("lithology-quick-hint")
        root.addWidget(hint)

        form = QFormLayout()
        self.top_input = self._depth_input(top_depth)
        self.top_input.setObjectName("lithology-quick-top")
        self.bottom_input = self._depth_input(bottom_depth)
        self.bottom_input.setObjectName("lithology-quick-bottom")
        self.lithotype_input = QComboBox()
        self.lithotype_input.setObjectName("lithology-quick-rock")
        self.lithotype_input.setEditable(False)
        for item in self.catalog:
            self.lithotype_input.addItem(
                self._icon(item.color),
                f"{item.localized_name(language.value)} ({item.code})",
                item.lithotype_id,
            )

        form.addRow(self._t("lithology.top"), self.top_input)
        form.addRow(self._t("lithology.bottom"), self.bottom_input)
        form.addRow(self._t("lithology.quick_rock"), self.lithotype_input)
        root.addLayout(form)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.setObjectName("lithology-quick-buttons")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._t("common.ok"))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            self._t("common.cancel")
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    @staticmethod
    def _depth_input(value: float) -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setRange(-100_000.0, 100_000.0)
        field.setDecimals(3)
        field.setSuffix(" m")
        field.setValue(float(value))
        return field

    @staticmethod
    def _icon(color: str) -> QIcon:
        pixmap = QPixmap(24, 16)
        pixmap.fill(QColor("transparent"))
        painter = QPainter(pixmap)
        painter.fillRect(1, 1, 22, 14, QColor(color))
        painter.setPen(QColor("#334155"))
        painter.drawRect(1, 1, 22, 14)
        painter.end()
        return QIcon(pixmap)

    @property
    def top_depth(self) -> float:
        return float(self.top_input.value())

    @property
    def bottom_depth(self) -> float:
        return float(self.bottom_input.value())

    @property
    def lithotype_id(self) -> str:
        value = self.lithotype_input.currentData()
        return str(value) if value is not None else ""
