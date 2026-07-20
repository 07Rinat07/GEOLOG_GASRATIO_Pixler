from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import InterpretationInterval, WellInterpretation
from geoworkbench.services.localization import AppLanguage, Localizer


class InterpretationPropertiesPanel(QWidget):
    """Editable properties for the interval selected on the tablet or in the manager."""

    update_requested = Signal(str, str, object)
    manager_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self._interpretation_id: str | None = None
        self._interval_id: str | None = None

        root = QVBoxLayout(self)
        self.empty_label = QLabel(self._t("interpretations.properties_empty"))
        self.empty_label.setWordWrap(True)
        root.addWidget(self.empty_label)

        self.form_widget = QWidget()
        form = QFormLayout(self.form_widget)
        self._form = form
        self.interpretation_label = QLabel()
        self.interpretation_label.setObjectName("interpretation-properties-name")
        self.top_input = self._depth_input("interpretation-properties-top")
        self.bottom_input = self._depth_input("interpretation-properties-bottom")
        self.type_input = QLineEdit()
        self.type_input.setObjectName("interpretation-properties-type")
        self.label_input = QLineEdit()
        self.label_input.setObjectName("interpretation-properties-label")
        self.color_input = QLineEdit()
        self.color_input.setObjectName("interpretation-properties-color")
        self.comment_input = QPlainTextEdit()
        self.comment_input.setObjectName("interpretation-properties-comment")
        self.comment_input.setMaximumHeight(110)
        for label, control in (
            (self._t("interpretations.name"), self.interpretation_label),
            (self._t("interpretations.top"), self.top_input),
            (self._t("interpretations.bottom"), self.bottom_input),
            (self._t("interpretations.type"), self.type_input),
            (self._t("interpretations.label"), self.label_input),
            (self._t("interpretations.color"), self.color_input),
            (self._t("interpretations.comment"), self.comment_input),
        ):
            form.addRow(label, control)
        root.addWidget(self.form_widget)

        self.apply_button = QPushButton(self._t("common.apply"))
        self.apply_button.setObjectName("interpretation-properties-apply")
        self.apply_button.clicked.connect(self._emit_update)
        root.addWidget(self.apply_button)

        self.manager_button = QPushButton(self._t("interpretations.open_manager"))
        self.manager_button.setObjectName("interpretation-properties-manager")
        self.manager_button.clicked.connect(self.manager_requested)
        root.addWidget(self.manager_button)
        root.addStretch(1)
        self.clear()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def set_language(self, language: AppLanguage) -> None:
        self.localizer = Localizer.create(language)
        self.empty_label.setText(self._t("interpretations.properties_empty"))
        for control, key in (
            (self.interpretation_label, "interpretations.name"),
            (self.top_input, "interpretations.top"),
            (self.bottom_input, "interpretations.bottom"),
            (self.type_input, "interpretations.type"),
            (self.label_input, "interpretations.label"),
            (self.color_input, "interpretations.color"),
            (self.comment_input, "interpretations.comment"),
        ):
            label = self._form.labelForField(control)
            if label is not None:
                label.setText(self._t(key))
        self.apply_button.setText(self._t("common.apply"))
        self.manager_button.setText(self._t("interpretations.open_manager"))

    @staticmethod
    def _depth_input(object_name: str) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setObjectName(object_name)
        control.setRange(-100_000.0, 100_000.0)
        control.setDecimals(3)
        return control

    def show_interval(
        self,
        interpretation: WellInterpretation,
        interval: InterpretationInterval,
    ) -> None:
        self._interpretation_id = interpretation.interpretation_id
        self._interval_id = interval.interval_id
        self.interpretation_label.setText(interpretation.name)
        self.top_input.setValue(interval.top_depth)
        self.bottom_input.setValue(interval.bottom_depth)
        self.type_input.setText(interval.interval_type)
        self.label_input.setText(interval.label)
        self.color_input.setText(interval.color)
        self.comment_input.setPlainText(interval.comment or "")
        self.empty_label.hide()
        self.form_widget.show()
        self.apply_button.setEnabled(True)
        self.manager_button.setEnabled(True)

    def clear(self) -> None:
        self._interpretation_id = None
        self._interval_id = None
        self.interpretation_label.clear()
        self.top_input.setValue(0.0)
        self.bottom_input.setValue(0.0)
        self.type_input.clear()
        self.label_input.clear()
        self.color_input.clear()
        self.comment_input.clear()
        self.empty_label.show()
        self.form_widget.hide()
        self.apply_button.setEnabled(False)
        self.manager_button.setEnabled(True)

    def _emit_update(self) -> None:
        if self._interpretation_id is None or self._interval_id is None:
            return
        self.update_requested.emit(
            self._interpretation_id,
            self._interval_id,
            {
                "top_depth": self.top_input.value(),
                "bottom_depth": self.bottom_input.value(),
                "interval_type": self.type_input.text(),
                "label": self.label_input.text(),
                "color": self.color_input.text(),
                "comment": self.comment_input.toPlainText(),
            },
        )
