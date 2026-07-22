from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.tablet.models import (
    CurveLineStyle,
    CurveStyle,
    TrackDefinition,
    TrackKind,
    XScale,
)
from geoworkbench.services.localization import AppLanguage, Localizer


class TrackInspector(QWidget):
    collapse_requested = Signal()
    settings_requested = Signal(str, int, str, object, object)
    curve_style_requested = Signal(str, str, str, float, str)
    grid_requested = Signal(str, bool, bool, float, int, int, bool)
    x_axis_label_requested = Signal(str, str)

    def __init__(self, *, language: AppLanguage = AppLanguage.RU) -> None:
        super().__init__()
        self.localizer = Localizer.create(language)
        self._track_id: str | None = None
        self._current_track: TrackDefinition | None = None
        self._stack = QStackedWidget()
        self.collapse_button = QPushButton(self._t("panel.hide_all"))
        self.collapse_button.setObjectName("inspector-collapse-button")
        self.collapse_button.clicked.connect(self.collapse_requested.emit)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._stack.addWidget(self._text)

        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        self._summary = QLabel()
        self._summary.setWordWrap(True)
        editor_layout.addWidget(self._summary)

        form = QFormLayout()
        self._main_form = form
        self.width_input = QSpinBox()
        self.width_input.setRange(80, 2000)
        form.addRow(self._t("inspector.width"), self.width_input)

        self.scale_input = QComboBox()
        self.scale_input.addItem(self._t("inspector.linear"), XScale.LINEAR.value)
        self.scale_input.addItem(self._t("inspector.logarithmic"), XScale.LOGARITHMIC.value)
        form.addRow(self._t("inspector.x_scale"), self.scale_input)

        self.auto_range_input = QCheckBox(self._t("common.auto"))
        self.auto_range_input.toggled.connect(self._update_range_enabled)
        form.addRow(self._t("inspector.x_range"), self.auto_range_input)

        self.minimum_input = self._range_spin_box()
        self.maximum_input = self._range_spin_box()
        form.addRow(self._t("inspector.x_minimum"), self.minimum_input)
        form.addRow(self._t("inspector.x_maximum"), self.maximum_input)
        editor_layout.addLayout(form)

        style_form = QFormLayout()
        self._style_form = style_form
        self.curve_input = QComboBox()
        self.curve_input.currentIndexChanged.connect(self._load_curve_style)
        style_form.addRow(self._t("inspector.style_curve"), self.curve_input)
        self.color_input = QLineEdit()
        self.color_input.setPlaceholderText("#2563eb")
        style_form.addRow(self._t("inspector.color"), self.color_input)
        self.line_width_input = QDoubleSpinBox()
        self.line_width_input.setRange(0.5, 10.0)
        self.line_width_input.setDecimals(1)
        style_form.addRow(self._t("inspector.line_width"), self.line_width_input)
        self.line_style_input = QComboBox()
        for style in CurveLineStyle:
            self.line_style_input.addItem(
                self._t(f"inspector.line_style.{style.value}"), style.value
            )
        style_form.addRow(self._t("inspector.line_style"), self.line_style_input)
        editor_layout.addLayout(style_form)
        self.style_button = QPushButton(self._t("inspector.apply_style"))
        self.style_button.clicked.connect(self._emit_curve_style)
        editor_layout.addWidget(self.style_button)

        grid_form = QFormLayout()
        self._grid_form = grid_form
        self.grid_x_input = QCheckBox(self._t("inspector.grid_x"))
        self.grid_y_input = QCheckBox(self._t("inspector.grid_y"))
        self.grid_major_input = QSpinBox()
        self.grid_major_input.setRange(1, 20)
        self.grid_minor_input = QSpinBox()
        self.grid_minor_input.setRange(1, 20)
        self.grid_alpha_input = QDoubleSpinBox()
        self.grid_alpha_input.setRange(0.0, 1.0)
        self.grid_alpha_input.setSingleStep(0.05)
        self.grid_alpha_input.setDecimals(2)
        grid_form.addRow(self.grid_x_input)
        grid_form.addRow(self.grid_y_input)
        grid_form.addRow(self._t("inspector.grid_major_divisions"), self.grid_major_input)
        grid_form.addRow(self._t("inspector.grid_minor_divisions"), self.grid_minor_input)
        grid_form.addRow(self._t("inspector.grid_alpha"), self.grid_alpha_input)
        self.grid_print_input = QCheckBox(self._t("inspector.grid_print"))
        grid_form.addRow(self.grid_print_input)
        editor_layout.addLayout(grid_form)
        self.grid_button = QPushButton(self._t("inspector.apply_grid"))
        self.grid_button.clicked.connect(self._emit_grid)
        editor_layout.addWidget(self.grid_button)

        axis_form = QFormLayout()
        self._axis_form = axis_form
        self.x_axis_label_input = QLineEdit()
        self.x_axis_label_input.setMaxLength(100)
        axis_form.addRow(self._t("inspector.x_axis_label"), self.x_axis_label_input)
        editor_layout.addLayout(axis_form)
        self.axis_label_button = QPushButton(self._t("inspector.apply_axis_label"))
        self.axis_label_button.clicked.connect(self._emit_x_axis_label)
        editor_layout.addWidget(self.axis_label_button)

        self.apply_button = QPushButton(self._t("common.apply"))
        self.apply_button.clicked.connect(self._emit_settings)
        editor_layout.addWidget(self.apply_button)
        editor_layout.addStretch(1)
        self._stack.addWidget(editor)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.addWidget(self.collapse_button)
        root.addWidget(self._stack)
        self.setPlainText(self._t("inspector.default"))

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def set_language(self, language: AppLanguage) -> None:
        previous_localizer = self.localizer
        self.localizer = Localizer.create(language)
        self.collapse_button.setText(self._t("panel.hide_all"))

        for field, key in (
            (self.width_input, "inspector.width"),
            (self.scale_input, "inspector.x_scale"),
            (self.auto_range_input, "inspector.x_range"),
            (self.minimum_input, "inspector.x_minimum"),
            (self.maximum_input, "inspector.x_maximum"),
        ):
            label = self._main_form.labelForField(field)
            if label is not None:
                label.setText(self._t(key))

        self.scale_input.setItemText(
            self.scale_input.findData(XScale.LINEAR.value),
            self._t("inspector.linear"),
        )
        self.scale_input.setItemText(
            self.scale_input.findData(XScale.LOGARITHMIC.value),
            self._t("inspector.logarithmic"),
        )
        self.auto_range_input.setText(self._t("common.auto"))

        for field, key in (
            (self.curve_input, "inspector.style_curve"),
            (self.color_input, "inspector.color"),
            (self.line_width_input, "inspector.line_width"),
            (self.line_style_input, "inspector.line_style"),
        ):
            label = self._style_form.labelForField(field)
            if label is not None:
                label.setText(self._t(key))
        for style in CurveLineStyle:
            row = self.line_style_input.findData(style.value)
            if row >= 0:
                self.line_style_input.setItemText(
                    row,
                    self._t(f"inspector.line_style.{style.value}"),
                )

        self.grid_x_input.setText(self._t("inspector.grid_x"))
        self.grid_y_input.setText(self._t("inspector.grid_y"))
        self.grid_print_input.setText(self._t("inspector.grid_print"))
        for field, key in (
            (self.grid_major_input, "inspector.grid_major_divisions"),
            (self.grid_minor_input, "inspector.grid_minor_divisions"),
        ):
            label = self._grid_form.labelForField(field)
            if label is not None:
                label.setText(self._t(key))
        grid_alpha_label = self._grid_form.labelForField(self.grid_alpha_input)
        if grid_alpha_label is not None:
            grid_alpha_label.setText(self._t("inspector.grid_alpha"))
        axis_label = self._axis_form.labelForField(self.x_axis_label_input)
        if axis_label is not None:
            axis_label.setText(self._t("inspector.x_axis_label"))

        self.style_button.setText(self._t("inspector.apply_style"))
        self.grid_button.setText(self._t("inspector.apply_grid"))
        self.axis_label_button.setText(self._t("inspector.apply_axis_label"))
        self.apply_button.setText(self._t("common.apply"))

        if self._current_track is not None:
            self.show_track(self._current_track)
        elif self._text.toPlainText() == previous_localizer.text("inspector.default"):
            self._text.setPlainText(self._t("inspector.default"))

    def setPlainText(self, text: str) -> None:  # noqa: N802
        self._track_id = None
        self._current_track = None
        self._text.setPlainText(text)
        self._stack.setCurrentIndex(0)

    def show_track(
        self,
        track: TrackDefinition,
        *,
        suggested_range: tuple[float, float] | None = None,
    ) -> None:
        self._track_id = track.track_id
        self._current_track = track
        kind_keys = {
            TrackKind.DEPTH: "tablet.track.depth",
            TrackKind.CURVE: "tablet.track.curve",
            TrackKind.GAS: "tablet.track.gas",
            TrackKind.DEXP: "tablet.track.dexp",
            TrackKind.LITHOLOGY: "tablet.track.lithology",
            TrackKind.CUTTINGS: "tablet.track.cuttings",
            TrackKind.CALCIMETRY: "tablet.track.calcimetry",
            TrackKind.LBA: "tablet.track.lba",
            TrackKind.STRATIGRAPHY: "tablet.track.stratigraphy",
            TrackKind.INTERPRETATION: "tablet.track.interpretation",
            TrackKind.TEXT: "tablet.track.description",
        }
        curve_names = [
            track.curve_display_settings(mnemonic).display_name or mnemonic
            for mnemonic in track.curve_mnemonics
        ]
        self._summary.setText(
            f"{track.title}\n"
            f"{self._t('inspector.type')}: {self._t(kind_keys[track.kind])}\n"
            f"{self._t('inspector.curves')}: "
            f"{', '.join(curve_names) or self._t('common.none')}"
        )
        self.width_input.setValue(track.width)
        self.scale_input.setCurrentIndex(self.scale_input.findData(track.x_scale.value))
        automatic = track.x_min is None or track.x_max is None
        self.auto_range_input.setChecked(automatic)
        fallback = suggested_range or (0.1, 100.0)
        self.minimum_input.setValue(track.x_min if track.x_min is not None else fallback[0])
        self.maximum_input.setValue(track.x_max if track.x_max is not None else fallback[1])
        self._update_range_enabled(automatic)
        self.curve_input.blockSignals(True)
        self.curve_input.clear()
        for mnemonic in track.curve_mnemonics:
            display_name = track.curve_display_settings(mnemonic).display_name or mnemonic
            self.curve_input.addItem(display_name, mnemonic)
        self.curve_input.blockSignals(False)
        self._load_curve_style(self.curve_input.currentIndex())
        self.style_button.setEnabled(bool(track.curve_mnemonics))
        self.grid_x_input.setChecked(track.grid_x)
        self.grid_y_input.setChecked(track.grid_y)
        self.grid_major_input.setValue(track.grid_major_divisions)
        self.grid_minor_input.setValue(track.grid_minor_divisions)
        self.grid_alpha_input.setValue(track.grid_alpha)
        self.grid_print_input.setChecked(track.grid_print)
        self.x_axis_label_input.setText(track.x_axis_label)
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

    def _load_curve_style(self, _index: int) -> None:
        track = self._current_track
        mnemonic = str(self.curve_input.currentData() or "")
        if track is None or not mnemonic:
            self.color_input.setText("")
            return
        style = track.curve_style(mnemonic) or CurveStyle()
        self.color_input.setText(style.color)
        self.line_width_input.setValue(style.width)
        self.line_style_input.setCurrentIndex(
            self.line_style_input.findData(style.line_style.value)
        )

    def _emit_curve_style(self) -> None:
        mnemonic = str(self.curve_input.currentData() or "")
        if self._track_id is None or not mnemonic:
            return
        self.curve_style_requested.emit(
            self._track_id,
            mnemonic,
            self.color_input.text().strip(),
            self.line_width_input.value(),
            str(self.line_style_input.currentData()),
        )

    def _emit_grid(self) -> None:
        if self._track_id is None:
            return
        self.grid_requested.emit(
            self._track_id,
            self.grid_x_input.isChecked(),
            self.grid_y_input.isChecked(),
            self.grid_alpha_input.value(),
            self.grid_major_input.value(),
            self.grid_minor_input.value(),
            self.grid_print_input.isChecked(),
        )

    def _emit_x_axis_label(self) -> None:
        if self._track_id is None:
            return
        self.x_axis_label_requested.emit(self._track_id, self.x_axis_label_input.text().strip())
