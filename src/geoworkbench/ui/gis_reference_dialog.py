"""Read-only operator workflow for one explicitly calibrated GIS source row."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from geoworkbench.domain.models import Dataset
from geoworkbench.services.gis_reference_calibration import (
    CalibratedGisSample, create_gis_reference_calibration, evaluate_gis_reference_sample,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.gis_reference_input_review import review_gis_reference_input
from geoworkbench.ui.gis_input_inventory_dialog import GisInputInventoryDialog
from geoworkbench.ui.window_geometry import fit_window_to_screen


class GisReferenceDialog(QDialog):
    def __init__(
        self, dataset: Dataset, parent: QWidget | None = None,
        *, language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.dataset = dataset
        self.localizer = Localizer.create(language)
        self.sample: CalibratedGisSample | None = None
        self.setObjectName("gis-reference-dialog")
        self.setWindowTitle(self._t("action"))
        root = QVBoxLayout(self)
        intro = QLabel(self._t("intro"), self)
        intro.setWordWrap(True)
        root.addWidget(intro)
        self.inventory_button = QPushButton(self._t("inventory"), self)
        self.inventory_button.setObjectName("gis-reference-inventory")
        self.inventory_button.clicked.connect(self._show_inventory)
        root.addWidget(self.inventory_button)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        body = QWidget(scroll)
        form = QFormLayout(body)
        self.method = QComboBox(body)
        self.method.addItem(self._t("choose"), None)
        self.method.addItem("IGR (API)", "igr-linear-1")
        self.method.addItem(self._t("density_method"), "density-porosity-1")
        form.addRow(self._t("method"), self.method)
        self.channel = QComboBox(body)
        self.channel.addItem(self._t("choose"), None)
        for key, curve in dataset.curves.items():
            self.channel.addItem(f"{key} [{curve.metadata.unit or '?'}]", key)
        form.addRow(self._t("channel"), self.channel)
        self.row = QSpinBox(body)
        depths = np.asarray(dataset.active_index.values)
        count = len(depths) if depths.ndim == 1 else 0
        self.row.setRange(1, max(1, min(count, 2_147_483_647)))
        form.addRow(self._t("row"), self.row)
        self.review_source = QPushButton(self._t("review_source"), body)
        form.addRow(self.review_source)
        self.source_review_label = QLabel(body)
        self.source_review_label.setTextFormat(Qt.TextFormat.PlainText)
        self.source_review_label.setWordWrap(True)
        self.source_review_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow(self.source_review_label)
        self.source_sample_label = QLabel(body)
        self.source_sample_label.setTextFormat(Qt.TextFormat.PlainText)
        self.source_sample_label.setWordWrap(True)
        self.source_sample_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow(self.source_sample_label)
        self.fields: dict[str, QLineEdit] = {}
        for key in ("calibration_id", "tool_id", "reviewer", "evidence", "top", "base"):
            field = QLineEdit(body)
            field.setObjectName(f"gis-reference-{key}")
            field.setMaxLength(2000 if key == "evidence" else 200)
            form.addRow(self._t(key), field)
            self.fields[key] = field
        self.parameter_labels = (QLabel(body), QLabel(body))
        self.parameters = (QLineEdit(body), QLineEdit(body))
        for label, field in zip(self.parameter_labels, self.parameters):
            field.setMaxLength(100)
            form.addRow(label, field)
        scroll.setWidget(body)
        root.addWidget(scroll)
        self.calculate = QPushButton(self._t("calculate"), self)
        root.addWidget(self.calculate)
        self.result_label = QLabel(self)
        self.result_label.setTextFormat(Qt.TextFormat.PlainText)
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.result_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self.localizer.text("common.close"),
        )
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.method.currentIndexChanged.connect(self._method_changed)
        self.channel.currentIndexChanged.connect(self._invalidate)
        self.channel.currentIndexChanged.connect(self.source_review_label.clear)
        self.method.currentIndexChanged.connect(self.source_review_label.clear)
        self.row.valueChanged.connect(self._invalidate)
        for selector in (self.method, self.channel):
            selector.currentIndexChanged.connect(self.source_sample_label.clear)
        self.row.valueChanged.connect(self.source_sample_label.clear)
        for field in (*self.fields.values(), *self.parameters):
            field.textChanged.connect(self._invalidate)
        self.calculate.clicked.connect(self._calculate)
        self.review_source.clicked.connect(self._review_source)
        self._method_changed()
        fit_window_to_screen(self, preferred=QSize(640, 620), minimum=QSize(380, 360))

    def _show_inventory(self) -> None:
        GisInputInventoryDialog(
            self.dataset, self, language=self.localizer.language,
        ).exec()
        if self.sample is None:
            # The modal inventory can outlive edits to an uncalibrated preview.
            # Refresh the exact selected row so stale source values never linger.
            self._review_source()
            return
        if self.sample is not None:
            try:
                # The modal event loop may outlive source edits. Retain the displayed
                # result only while its original calibration still validates.
                evaluate_gis_reference_sample(
                    self.dataset, self.sample.calibration, sample_index=self.sample.sample_index,
                )
            except ValueError:
                self._review_source()
                self.result_label.setText(self._t("invalid"))

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(f"petro_reference.{key}", **values)

    def _invalidate(self) -> None:
        self.sample = None
        self.result_label.clear()

    def _review_source(self) -> None:
        self._invalidate()
        self.source_sample_label.clear()
        method, channel = self.method.currentData(), self.channel.currentData()
        if not isinstance(method, str) or not isinstance(channel, str):
            self.source_review_label.setText(self._t("selection_required"))
            return
        try:
            review = review_gis_reference_input(
                self.dataset, method_id=method, curve_key=channel,
            )
        except ValueError:
            self.source_review_label.setText(self._t("invalid"))
            return
        if review.ready_for_calibration:
            self.source_review_label.setText(self._t("source_ready"))
            index = self.row.value() - 1
            depths = self.dataset.active_index.values
            values = self.dataset.curves[channel].values
            # The fresh review validates shapes, axis and units; never substitute a nearby row.
            if not 0 <= index < len(depths) or not (
                np.isfinite(depths[index]) and np.isfinite(values[index])
            ):
                self.source_sample_label.setText(self._t("sample_unavailable"))
            else:
                self.source_sample_label.setText(self._t(
                    "source_sample", row=index + 1, md=f"{depths[index]:.9g}",
                    value=f"{values[index]:.9g}", unit=review.curve.unit if review.curve else "",
                ))
            return
        reasons = []
        for issue in review.issues:
            if issue.startswith(("axis:", "curve:")) or issue == "missing_curve_id":
                key = f"gis_inventory.issue.{issue.split(':', 1)[-1]}"
            else:
                key = f"petro_reference.issue.{issue}"
            reason = self.localizer.catalog.get(key, self._t("invalid"))
            if reason not in reasons:
                reasons.append(reason)
        self.source_review_label.setText(self._t("source_blocked", reasons="\n".join(reasons)))

    def _method_changed(self) -> None:
        density = self.method.currentData() == "density-porosity-1"
        labels = ("matrix", "fluid") if density else ("clean", "shale")
        for label, field, key in zip(self.parameter_labels, self.parameters, labels):
            label.setText(self._t(key))
            field.clear()
        self._invalidate()

    @staticmethod
    def _number(field: QLineEdit) -> float:
        # Explicit decimal separators only; no grouping/implicit unit conversion.
        return float(field.text().strip().replace(",", "."))

    def _calculate(self) -> None:
        # Recheck live source quality; a prior operator review never authorizes calculation.
        self._review_source()
        method, channel = self.method.currentData(), self.channel.currentData()
        if not isinstance(method, str) or not isinstance(channel, str):
            self.result_label.setText(self._t("selection_required"))
            return
        names = (("matrix_density_g_cm3", "fluid_density_g_cm3")
                 if method == "density-porosity-1"
                 else ("clean_reference_api", "shale_reference_api"))
        try:
            calibration = create_gis_reference_calibration(
                self.dataset, method_id=method, curve_key=channel,
                calibration_id=self.fields["calibration_id"].text(),
                tool_id=self.fields["tool_id"].text(), reviewer=self.fields["reviewer"].text(),
                applicability_reference=self.fields["evidence"].text(),
                md_top_m=self._number(self.fields["top"]),
                md_base_m=self._number(self.fields["base"]),
                parameters={key: self._number(field) for key, field in zip(names, self.parameters)},
            )
            sample = evaluate_gis_reference_sample(
                self.dataset, calibration, sample_index=self.row.value() - 1,
            )
        except ValueError:
            self.result_label.setText(self._t("invalid"))
            return
        self.sample = sample
        self.result_label.setText(self._t(
            "result", md=f"{sample.md_m:.9g}", value=f"{sample.source_value:.9g}",
            unit=calibration.source.curve.unit if calibration.source.curve else "",
            estimate=f"{sample.estimate.value:.9g}",
            quality=self._t(sample.estimate.quality.value),
            calibration=calibration.calibration_id,
        ))
