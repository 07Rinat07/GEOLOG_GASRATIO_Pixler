"""Read-only operator review of one saved lithology source."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from geoworkbench.project.session import ProjectSession
from geoworkbench.services.gis_gti_lithology_screening import ObservationQuality, RockFamily
from geoworkbench.services.lithology_source_mapping import (
    LithologySource, ReviewedLithologyMapping, create_lithology_mapping,
    evaluate_lithology_mapping, review_lithology_source,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.lithology_review_export import export_lithology_review
from geoworkbench.services.lithology_review_reader import (
    SavedLithologyReview, ReviewSourceStatus, compare_review_source, load_lithology_review,
)
from geoworkbench.ui.window_geometry import fit_window_to_screen


class LithologyMappingDialog(QDialog):
    def __init__(
        self, session: ProjectSession, parent: QWidget | None = None,
        *, language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.localizer = Localizer.create(language)
        self._source: LithologySource | None = None
        self._mapping: ReviewedLithologyMapping | None = None
        self.setObjectName("lithology-mapping-dialog")
        self.setWindowTitle(self._t("action"))
        root = QVBoxLayout(self)
        intro = QLabel(self._t("intro"), self)
        intro.setWordWrap(True)
        root.addWidget(intro)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        body = QWidget(scroll)
        form = QFormLayout(body)
        self.source = QComboBox(body)
        form.addRow(self._t("source"), self.source)
        self.reload = QPushButton(self._t("reload"), body)
        form.addRow(self.reload)
        self.source_label = QLabel(body)
        self.source_label.setTextFormat(Qt.TextFormat.PlainText)
        self.source_label.setWordWrap(True)
        form.addRow(self.source_label)
        self.family = QComboBox(body)
        self.family.addItem(self._t("choose"), None)
        for family in RockFamily:
            self.family.addItem(self._t(f"family.{family.value}"), family.value)
        form.addRow(self._t("family"), self.family)
        self.quality = QComboBox(body)
        self.quality.addItem(self._t("choose"), None)
        for quality in ObservationQuality:
            self.quality.addItem(self._t(f"quality.{quality.value}"), quality.value)
        form.addRow(self._t("quality"), self.quality)
        self.fields: dict[str, QLineEdit] = {}
        for key in ("mapping_id", "reviewer", "evidence"):
            field = QLineEdit(body)
            field.setMaxLength(2000 if key == "evidence" else 200)
            form.addRow(self._t(key), field)
            self.fields[key] = field
            field.textChanged.connect(self._invalidate)
        scroll.setWidget(body)
        root.addWidget(scroll)
        self.review = QPushButton(self._t("review"), self)
        root.addWidget(self.review)
        self.result_label = QLabel(self)
        self.result_label.setTextFormat(Qt.TextFormat.PlainText)
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.result_label)
        self.export = QPushButton(self._t("export"), self)
        self.export.setEnabled(False)
        root.addWidget(self.export)
        self.export_status = QLabel(self)
        self.export_status.setTextFormat(Qt.TextFormat.PlainText)
        self.export_status.setWordWrap(True)
        root.addWidget(self.export_status)
        self.open_record = QPushButton(self._t("open_record"), self)
        root.addWidget(self.open_record)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self.localizer.text("common.close"),
        )
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.source.currentIndexChanged.connect(self._select_source)
        self.family.currentIndexChanged.connect(self._invalidate)
        self.quality.currentIndexChanged.connect(self._invalidate)
        self.reload.clicked.connect(self._reload_sources)
        self.review.clicked.connect(self._review)
        self.export.clicked.connect(self._export)
        self.open_record.clicked.connect(self._open_record)
        self._reload_sources()
        fit_window_to_screen(self, preferred=QSize(660, 620), minimum=QSize(380, 360))

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(f"lithology_mapping.{key}", **values)

    @property
    def mapping(self) -> ReviewedLithologyMapping | None:
        # Consumers must never receive a review whose source changed in the meantime.
        if self._mapping is not None:
            try:
                evaluate_lithology_mapping(self.session, self._mapping)
            except (ValueError, TypeError, OverflowError):
                self._invalidate()
                self.result_label.setText(self._t("invalid"))
        return self._mapping

    def _invalidate(self) -> None:
        self._mapping = None
        self.result_label.clear()
        self.export.setEnabled(False)
        self.export_status.clear()

    def _reload_sources(self) -> None:
        self.source.clear()
        self.source.addItem(self._t("choose"), None)
        well = self.session.current_well
        if well is not None:
            for interval in well.lithology:
                self.source.addItem(
                    f"{interval.interval_id}: {interval.top_depth}–{interval.bottom_depth} m"
                    f" [{interval.lithotype_id}]", interval.interval_id,
                )
        self.source.setCurrentIndex(0)
        self._select_source()

    def _select_source(self) -> None:
        self._invalidate()
        self.family.setCurrentIndex(0)
        self.quality.setCurrentIndex(0)
        self._source = None
        self.source_label.clear()
        identity = self.source.currentData()
        if not isinstance(identity, str):
            return
        try:
            source = review_lithology_source(self.session, interval_id=identity)
        except (ValueError, TypeError, OverflowError):
            self.source_label.setText(self._t("invalid"))
            return
        self._source = source
        self.source_label.setText(self._t(
            "source_details", source=source.interval_id, lithotype=source.lithotype_id,
            top=f"{source.top_md_m:.9g}", bottom=f"{source.bottom_md_m:.9g}",
            axis=source.depth_axis_id,
        ))

    def _review(self) -> None:
        self._invalidate()
        family, quality = self.family.currentData(), self.quality.currentData()
        if self._source is None or family is None or quality is None:
            self.result_label.setText(self._t("selection_required"))
            return
        try:
            family, quality = RockFamily(family), ObservationQuality(quality)
            mapping = create_lithology_mapping(
                self.session, self._source,
                mapping_id=self.fields["mapping_id"].text(),
                reviewer=self.fields["reviewer"].text(),
                applicability_reference=self.fields["evidence"].text(),
                rock_family=family, quality=quality,
            )
            evaluate_lithology_mapping(self.session, mapping)
        except (ValueError, TypeError, OverflowError):
            self.result_label.setText(self._t("invalid"))
            return
        self._mapping = mapping
        self.export.setEnabled(True)
        self.result_label.setText(self._t(
            "result", mapping=mapping.mapping_id, source=mapping.source.interval_id,
            family=self._t(f"family.{family.value}"), quality=self._t(f"quality.{quality.value}"),
        ))

    def _export(self) -> None:
        if self.mapping is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, self._t("export"), "lithology-review.json", "JSON (*.json)",
        )
        if not filename:
            return
        mapping = self.mapping
        if mapping is None:
            return
        if not filename.casefold().endswith(".json"):
            filename += ".json"
        try:
            export_lithology_review(self.session, mapping, filename, overwrite=True)
        except (ValueError, TypeError, OverflowError):
            self._invalidate()
            self.result_label.setText(self._t("invalid"))
        except OSError:
            self.export_status.setText(self._t("export_failed"))
        else:
            self.export_status.setText(self._t("exported"))

    def _open_record(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, self._t("open_record"), "", "JSON (*.json)",
        )
        if not filename:
            return
        try:
            record = load_lithology_review(filename)
            status = compare_review_source(self.session, record)
        except (OSError, ValueError, TypeError, OverflowError):
            self.export_status.setText(self._t("record_invalid"))
            return
        SavedLithologyReviewDialog(record, status, self, language=self.localizer.language).exec()


class SavedLithologyReviewDialog(QDialog):
    """An archival viewer with no route to the active mapping fields."""

    def __init__(
        self, record: SavedLithologyReview, status: ReviewSourceStatus,
        parent: QWidget | None = None, *, language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.record = record
        self.status = status
        localizer = Localizer.create(language)

        def text(key: str, **values: object) -> str:
            return localizer.text(f"lithology_mapping.{key}", **values)

        self.setWindowTitle(text("open_record"))
        root = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        self.details = QLabel(text(
            "record_details", project=record.project_id, recorded=record.recorded_at_utc,
            mapping=record.mapping_id, reviewer=record.reviewer,
            evidence=record.applicability_reference, source=record.source.interval_id,
            lithotype=record.source.lithotype_id, axis=record.source.depth_axis_id,
            well=record.source.well_id, dataset=record.source.dataset_id,
            source_hash=record.source.source_sha256, axis_hash=record.source.axis_sha256,
            top=f"{record.source.top_md_m:.9g}", bottom=f"{record.source.bottom_md_m:.9g}",
            family=text(f"family.{record.rock_family.value}"),
            quality=text(f"quality.{record.quality.value}"), status=text(f"record_status.{status.value}"),
        ), self)
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.details.setMargin(8)
        self.details.setWordWrap(True)
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        scroll.setWidget(self.details)
        root.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(localizer.text("common.close"))
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        fit_window_to_screen(self, preferred=QSize(660, 560), minimum=QSize(380, 360))
