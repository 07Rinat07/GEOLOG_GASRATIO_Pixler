"""Read-only operator workflow for one explicitly calibrated GIS source row."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from geoworkbench.domain.models import Dataset
from geoworkbench.services.gis_calibration_records import (
    SavedGisCalibrationRecord, export_gis_calibration_record, load_gis_calibration_record,
    validate_gis_calibration_record_source,
)
from geoworkbench.services.gis_reference_calibration import (
    CalibratedGisSample, create_gis_reference_calibration, evaluate_gis_reference_sample,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.gis_reference_input_review import review_gis_reference_input
from geoworkbench.services.gis_interval_sample_review import review_gis_interval_samples
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
        self._loaded_record: SavedGisCalibrationRecord | None = None
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
        self.review_interval = QPushButton(self._t("review_interval"), body)
        self.review_interval.setObjectName("gis-reference-review-interval")
        form.addRow(self.review_interval)
        self.interval_review_label = QLabel(body)
        self.interval_review_label.setObjectName("gis-reference-interval-review")
        self.interval_review_label.setTextFormat(Qt.TextFormat.PlainText)
        self.interval_review_label.setWordWrap(True)
        self.interval_review_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow(self.interval_review_label)
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
        records = QHBoxLayout()
        self.save_parameters = QPushButton(self._t("save_parameters"), self)
        self.save_parameters.setObjectName("gis-reference-save-parameters")
        self.save_parameters.setEnabled(False)
        records.addWidget(self.save_parameters)
        self.open_parameters = QPushButton(self._t("open_parameters"), self)
        self.open_parameters.setObjectName("gis-reference-open-parameters")
        records.addWidget(self.open_parameters)
        root.addLayout(records)
        self.record_status = QLabel(self)
        self.record_status.setTextFormat(Qt.TextFormat.PlainText)
        self.record_status.setWordWrap(True)
        root.addWidget(self.record_status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self.localizer.text("common.close"),
        )
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.method.currentIndexChanged.connect(self._method_changed)
        self.channel.currentIndexChanged.connect(self._discard_record)
        self.channel.currentIndexChanged.connect(self.source_review_label.clear)
        self.method.currentIndexChanged.connect(self.source_review_label.clear)
        self.row.valueChanged.connect(self._invalidate)
        for selector in (self.method, self.channel):
            selector.currentIndexChanged.connect(self.source_sample_label.clear)
        self.row.valueChanged.connect(self.source_sample_label.clear)
        for field in (*self.fields.values(), *self.parameters):
            field.textChanged.connect(self._discard_record)
        self.calculate.clicked.connect(self._calculate)
        self.review_source.clicked.connect(self._review_source)
        self.review_interval.clicked.connect(self._review_interval)
        for selector in (self.method, self.channel):
            selector.currentIndexChanged.connect(self.interval_review_label.clear)
        for key in ("top", "base"):
            self.fields[key].textChanged.connect(self.interval_review_label.clear)
        self.save_parameters.clicked.connect(self._save_parameters)
        self.open_parameters.clicked.connect(self._open_parameters)
        self._method_changed()
        fit_window_to_screen(self, preferred=QSize(640, 620), minimum=QSize(380, 360))

    def _show_inventory(self) -> None:
        self.interval_review_label.clear()
        GisInputInventoryDialog(
            self.dataset, self, language=self.localizer.language,
        ).exec()
        # Keep the selected key (even if it disappeared) so a new channel is
        # never silently substituted for an operator's reviewed source.
        for key, curve in self.dataset.curves.items():
            index = self.channel.findData(key)
            label = f"{key} [{curve.metadata.unit or '?'}]"
            if index < 0:
                self.channel.addItem(label, key)
            elif self.channel.itemText(index) != label:
                self.channel.setItemText(index, label)
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

    def _review_interval(self) -> None:
        self.interval_review_label.clear()
        method, channel = self.method.currentData(), self.channel.currentData()
        if not isinstance(method, str) or not isinstance(channel, str):
            self.interval_review_label.setText(self._t("selection_required"))
            return
        try:
            result = review_gis_interval_samples(
                self.dataset, method_id=method, curve_key=channel,
                top_md_m=self._number(self.fields["top"]),
                bottom_md_m=self._number(self.fields["base"]),
            )
        except (ValueError, TypeError, OverflowError):
            self.interval_review_label.setText(self._t("interval_invalid"))
            return
        summary = self._t(
            "interval_summary", total=result.sample_count,
            finite=result.finite_count, missing=result.missing_count,
        )
        if result.finite_value_bounds is not None:
            minimum, maximum = result.finite_value_bounds
            curve = result.source.curve
            summary += "\n" + self._t(
                "interval_value_bounds", minimum=f"{minimum:.9g}", maximum=f"{maximum:.9g}",
                unit=(curve.unit if curve is not None else None) or "?",
            )
        if result.missing_md_preview:
            summary += "\n" + self._t(
                "interval_missing_depths",
                shown=len(result.missing_md_preview), total=result.missing_count,
                depths=", ".join(f"{depth:.9g}" for depth in result.missing_md_preview),
            )
        self.interval_review_label.setText(summary)

    def _invalidate(self) -> None:
        self.sample = None
        self.result_label.clear()
        self.save_parameters.setEnabled(False)
        self.record_status.clear()

    def _discard_record(self) -> None:
        self._loaded_record = None
        self._invalidate()

    def _current_sample(self) -> CalibratedGisSample | None:
        if self.sample is not None:
            try:
                evaluate_gis_reference_sample(
                    self.dataset, self.sample.calibration, sample_index=self.sample.sample_index,
                )
            except (ValueError, TypeError, OverflowError):
                self._invalidate()
                self.result_label.setText(self._t("invalid"))
        return self.sample

    def _save_parameters(self) -> None:
        sample = self._current_sample()
        if sample is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, self._t("save_parameters"), "gis-parameters.json", "JSON (*.json)",
        )
        if not filename:
            return
        # A native dialog runs an event loop; do not export a replacement review or draft.
        if self._current_sample() is not sample:
            return
        if not filename.casefold().endswith(".json"):
            filename += ".json"
            # The native chooser confirmed the selected path, not an appended suffix.
            if Path(filename).exists():
                answer = QMessageBox.question(
                    self, self._t("save_parameters"), self._t("parameters_overwrite"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer is not QMessageBox.StandardButton.Yes:
                    return
        if self._current_sample() is not sample:
            return
        try:
            export_gis_calibration_record(
                self.dataset, sample.calibration, filename, overwrite=True,
            )
        except (ValueError, TypeError, OverflowError):
            self._invalidate()
            self.record_status.setText(self._t("parameters_invalid"))
        except OSError:
            self.record_status.setText(self._t("parameters_save_failed"))
        else:
            self.record_status.setText(self._t("parameters_saved"))

    def _open_parameters(self) -> None:
        dataset = self.dataset
        filename, _ = QFileDialog.getOpenFileName(
            self, self._t("open_parameters"), "", "JSON (*.json)",
        )
        if not filename:
            return
        try:
            if self.dataset is not dataset:
                raise ValueError("Dataset changed during parameter selection")
            record = load_gis_calibration_record(filename, dataset=dataset)
            method_index = self.method.findData(record.method_id)
            channel_index = self.channel.findData(record.curve_key)
            if method_index < 1 or channel_index < 1:
                raise ValueError("Recorded source selection is unavailable")
            fields = {
                "calibration_id": record.calibration_id, "tool_id": record.tool_id,
                "reviewer": record.reviewer, "evidence": record.applicability_reference,
                "top": repr(record.md_bounds[0]), "base": repr(record.md_bounds[1]),
            }
            parameters = dict(record.parameters)
            parameter_values = tuple(
                repr(parameters[name]) for name in self._parameter_names(record.method_id)
            )
            if any(len(value) > self.fields[key].maxLength() for key, value in fields.items()):
                raise ValueError("Recorded text exceeds editor limits")
            validate_gis_calibration_record_source(dataset, record)
            if self.dataset is not dataset:
                raise ValueError("Dataset changed while reading parameters")
        except (OSError, ValueError, TypeError, OverflowError, KeyError):
            self._current_sample()
            self.record_status.setText(self._t("parameters_invalid"))
            return
        # Commit only a fully checked record. Loading never creates a runtime calibration.
        self._invalidate()
        self.method.setCurrentIndex(method_index)
        self.channel.setCurrentIndex(channel_index)
        for key, value in fields.items():
            self.fields[key].setText(value)
        for field, value in zip(self.parameters, parameter_values):
            field.setText(value)
        self._review_source()
        self._loaded_record = record
        self.record_status.setText(self._t("parameters_loaded"))

    def _review_source(self) -> None:
        self.interval_review_label.clear()
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
            # Expose new rows without clamping a removed selection to a neighbour.
            self.row.setMaximum(max(self.row.value(), min(len(depths), 2_147_483_647)))
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
        self._discard_record()

    @staticmethod
    def _number(field: QLineEdit) -> float:
        # Explicit decimal separators only; no grouping/implicit unit conversion.
        return float(field.text().strip().replace(",", "."))

    @staticmethod
    def _parameter_names(method: str) -> tuple[str, str]:
        return (("matrix_density_g_cm3", "fluid_density_g_cm3")
                if method == "density-porosity-1"
                else ("clean_reference_api", "shale_reference_api"))

    def _calculate(self) -> None:
        if self._loaded_record is not None:
            try:
                validate_gis_calibration_record_source(self.dataset, self._loaded_record)
            except (ValueError, TypeError, OverflowError):
                self._invalidate()
                self.record_status.setText(self._t("parameters_invalid"))
                return
        # Recheck live source quality; a prior operator review never authorizes calculation.
        self._review_source()
        method, channel = self.method.currentData(), self.channel.currentData()
        if not isinstance(method, str) or not isinstance(channel, str):
            self.result_label.setText(self._t("selection_required"))
            return
        names = self._parameter_names(method)
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
        self.save_parameters.setEnabled(True)
        self.result_label.setText(self._t(
            "result", md=f"{sample.md_m:.9g}", value=f"{sample.source_value:.9g}",
            unit=calibration.source.curve.unit if calibration.source.curve else "",
            estimate=f"{sample.estimate.value:.9g}",
            quality=self._t(sample.estimate.quality.value),
            calibration=calibration.calibration_id,
        ))
