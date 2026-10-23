"""Read-only operator review of one saved lithology source."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHeaderView, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
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
from geoworkbench.services.lithology_review_history import (
    LithologyHistoryEntry, load_lithology_review_history,
)
from geoworkbench.services.lithology_review_comparison import (
    LithologyReviewComparison, compare_lithology_review_records,
)
from geoworkbench.services.lithology_revision_proposal import (
    LithologyRevisionProposal, prepare_lithology_revision_proposal,
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
        self.open_history = QPushButton(self._t("open_history"), self)
        root.addWidget(self.open_history)
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
        self.open_history.clicked.connect(self._open_history)
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

    def _open_history(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(
            self, self._t("open_history"), "", "JSON (*.json)",
        )
        if not filenames:
            return
        try:
            entries = load_lithology_review_history(self.session, tuple(filenames))
        except (OSError, ValueError, TypeError, OverflowError):
            self.export_status.setText(self._t("history_invalid"))
            return
        LithologyReviewHistoryDialog(
            self.session, entries, self, language=self.localizer.language,
        ).exec()


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


class LithologyReviewHistoryDialog(QDialog):
    def __init__(
        self, session: ProjectSession, entries: tuple[LithologyHistoryEntry, ...],
        parent: QWidget | None = None, *, language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        if not entries:
            raise ValueError("History viewer requires at least one record")
        self.session, self.entries, self.language = session, entries, language
        localizer = Localizer.create(language)
        self._text = lambda key: localizer.text(f"lithology_mapping.{key}")
        self.setWindowTitle(self._text("open_history"))
        root = QVBoxLayout(self)
        intro = QLabel(self._text("history_intro"), self)
        intro.setWordWrap(True)
        root.addWidget(intro)
        first = entries[0].record
        scope = QLabel(localizer.text(
            "lithology_mapping.history_scope", project=first.project_id,
            well=first.source.well_id, dataset=first.source.dataset_id,
            axis=first.source.depth_axis_id, source=first.source.interval_id,
        ), self)
        scope.setTextFormat(Qt.TextFormat.PlainText)
        scope.setWordWrap(True)
        root.addWidget(scope)
        self.table = QTableWidget(len(entries), 6, self)
        self.table.setHorizontalHeaderLabels([
            self._text(key) for key in (
                "history_time", "history_id", "history_reviewer", "history_family",
                "history_quality", "history_source",
            )
        ])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for column, width in enumerate((205, 110, 110, 125, 135, 150)):
            self.table.setColumnWidth(column, width)
        for row, entry in enumerate(entries):
            record = entry.record
            values = (
                record.recorded_at_utc, record.mapping_id, record.reviewer,
                self._text(f"family.{record.rock_family.value}"),
                self._text(f"quality.{record.quality.value}"),
                self._text(f"history_status.{entry.source_status.value}"),
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.clearSelection()
        root.addWidget(self.table)
        self.details = QPushButton(self._text("history_details"), self)
        self.details.setEnabled(False)
        self.compare = QPushButton(self._text("history_compare"), self)
        self.compare.setEnabled(False)
        self.propose = QPushButton(self._text("proposal_action"), self)
        self.propose.setEnabled(False)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.details.clicked.connect(self._open_selected)
        self.table.cellDoubleClicked.connect(self._open_selected)
        self.compare.clicked.connect(self._compare_selected)
        self.propose.clicked.connect(self._propose_selected)
        root.addWidget(self.details)
        root.addWidget(self.compare)
        root.addWidget(self.propose)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(localizer.text("common.close"))
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        fit_window_to_screen(self, preferred=QSize(900, 560), minimum=QSize(380, 360))

    def _open_selected(self, *_args: object) -> None:
        selected = self.table.selectionModel().selectedRows()
        if len(selected) != 1:
            return
        record = self.entries[selected[0].row()].record
        status = compare_review_source(self.session, record)
        SavedLithologyReviewDialog(record, status, self, language=self.language).exec()


    def _selection_changed(self) -> None:
        count = len(self.table.selectionModel().selectedRows())
        self.details.setEnabled(count == 1)
        self.compare.setEnabled(count == 2)
        self.propose.setEnabled(count == 2)

    def _propose_selected(self) -> None:
        rows = sorted(index.row() for index in self.table.selectionModel().selectedRows())
        if len(rows) != 2:
            return
        LithologyRevisionProposalDialog(
            self.entries[rows[0]].record, self.entries[rows[1]].record,
            self, session=self.session, language=self.language,
        ).exec()

    def _compare_selected(self) -> None:
        rows = sorted(index.row() for index in self.table.selectionModel().selectedRows())
        if len(rows) != 2:
            return
        comparison = compare_lithology_review_records(
            self.entries[rows[0]].record, self.entries[rows[1]].record,
        )
        LithologyReviewComparisonDialog(
            comparison, self, language=self.language,
        ).exec()


class LithologyReviewComparisonDialog(QDialog):
    """Show only field differences between two explicitly selected archival records."""

    def __init__(
        self, comparison: LithologyReviewComparison, parent: QWidget | None = None,
        *, language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.comparison = comparison
        localizer = Localizer.create(language)

        def translate(key: str, **values: object) -> str:
            return localizer.text(f"lithology_mapping.{key}", **values)

        self.setWindowTitle(translate("history_compare"))
        root = QVBoxLayout(self)
        intro = QLabel(translate("comparison_intro"), self)
        intro.setWordWrap(True)
        root.addWidget(intro)
        first = QLabel(translate(
            "comparison_record", time=comparison.first.recorded_at_utc,
            mapping=comparison.first.mapping_id,
        ), self)
        second = QLabel(translate(
            "comparison_record", time=comparison.second.recorded_at_utc,
            mapping=comparison.second.mapping_id,
        ), self)
        for label in (first, second):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            root.addWidget(label)
        self.table: QTableWidget | None
        if comparison.differences:
            self.table = QTableWidget(len(comparison.differences), 3, self)
            self.table.setHorizontalHeaderLabels([
                translate("comparison_field"),
                translate("comparison_first"),
                translate("comparison_second"),
            ])
            self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            for column, width in enumerate((170, 300, 300)):
                self.table.setColumnWidth(column, width)
            for row, difference in enumerate(comparison.differences):
                values = (
                    translate(f"comparison_field.{difference.field_name}"),
                    difference.first_value, difference.second_value,
                )
                for column, value in enumerate(values):
                    self.table.setItem(row, column, QTableWidgetItem(value))
            root.addWidget(self.table)
        else:
            self.table = None
            message = QLabel(translate("comparison_no_differences"), self)
            message.setTextFormat(Qt.TextFormat.PlainText)
            message.setWordWrap(True)
            root.addWidget(message)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            localizer.text("common.close"),
        )
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        fit_window_to_screen(self, preferred=QSize(900, 560), minimum=QSize(380, 360))


class LithologyRevisionProposalDialog(QDialog):
    """Preview an explicit operator proposal without approving or persisting it."""

    def __init__(
        self, first: SavedLithologyReview, second: SavedLithologyReview,
        parent: QWidget | None = None, *,
        session: ProjectSession, language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.records = (first, second)
        self.localizer = Localizer.create(language)
        self.proposal: LithologyRevisionProposal | None = None
        self.setWindowTitle(self._t("proposal_action"))
        root = QVBoxLayout(self)
        intro = QLabel(self._t("proposal_intro"), self)
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.PlainText)
        root.addWidget(intro)

        form = QFormLayout()
        self.baseline = QComboBox(self)
        self.baseline.addItem(self._t("proposal_choose_baseline"), None)
        for number, record in enumerate(self.records, 1):
            self.baseline.addItem(self._t(
                "proposal_record", number=number, mapping=record.mapping_id,
                time=record.recorded_at_utc,
            ), number - 1)
        form.addRow(self._t("proposal_baseline"), self.baseline)

        self.proposal_id = QLineEdit(self)
        self.proposal_id.setMaxLength(128)
        form.addRow(self._t("proposal_id"), self.proposal_id)
        self.proposed_by = QLineEdit(self)
        self.proposed_by.setMaxLength(128)
        form.addRow(self._t("proposal_by"), self.proposed_by)
        self.justification = QPlainTextEdit(self)
        self.justification.setMaximumHeight(90)
        form.addRow(self._t("proposal_justification"), self.justification)
        root.addLayout(form)

        self.prepare = QPushButton(self._t("proposal_prepare"), self)
        root.addWidget(self.prepare)
        self.summary = QLabel(self)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.summary)
        self.source_status = QLabel(self)
        self.source_status.setTextFormat(Qt.TextFormat.PlainText)
        self.source_status.setWordWrap(True)
        self.source_status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse,
        )
        root.addWidget(self.source_status)
        self.source_warning = QLabel(self)
        self.source_warning.setTextFormat(Qt.TextFormat.PlainText)
        self.source_warning.setWordWrap(True)
        self.source_warning.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse,
        )
        root.addWidget(self.source_warning)
        self.preview = QTableWidget(0, 3, self)
        self.preview.setHorizontalHeaderLabels([
            self._t("comparison_field"), self._t("comparison_first"),
            self._t("comparison_second"),
        ])
        self.preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for col, width in enumerate((170, 290, 290)):
            self.preview.setColumnWidth(col, width)
        self.preview.hide()
        self.provenance = QTableWidget(0, 3, self)
        self.provenance.setHorizontalHeaderLabels([
            self._t("comparison_field"), self._t("proposal_baseline"),
            self._t("proposal_candidate"),
        ])
        self.provenance.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self.provenance.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive,
        )
        for col, width in enumerate((170, 290, 290)):
            self.provenance.setColumnWidth(col, width)
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self.preview, self._t("proposal_changes_tab"))
        self.tabs.addTab(self.provenance, self._t("proposal_sources_tab"))
        self.tabs.hide()
        self.preview.hide()  # QTabWidget may expose its initially selected page.
        root.addWidget(self.tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            self.localizer.text("common.close"),
        )
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.baseline.currentIndexChanged.connect(self._invalidate)
        self.proposal_id.textChanged.connect(self._invalidate)
        self.proposed_by.textChanged.connect(self._invalidate)
        self.justification.textChanged.connect(self._invalidate)
        self.prepare.clicked.connect(self._prepare)
        fit_window_to_screen(self, preferred=QSize(880, 650), minimum=QSize(380, 360))

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(f"lithology_mapping.{key}", **values)

    def _invalidate(self) -> None:
        self.proposal = None
        self.summary.clear()
        self.source_status.clear()
        self.source_warning.clear()
        self.preview.setRowCount(0)
        self.provenance.setRowCount(0)
        self.tabs.setCurrentIndex(0)
        self.tabs.hide()
        self.preview.hide()

    def _prepare(self) -> None:
        self._invalidate()
        index = self.baseline.currentData()
        if type(index) is not int or index not in (0, 1):
            self.summary.setText(self._t("proposal_invalid"))
            return
        baseline, candidate = self.records[index], self.records[1 - index]
        try:
            proposal = prepare_lithology_revision_proposal(
                baseline, candidate, proposal_id=self.proposal_id.text(),
                proposed_by=self.proposed_by.text(),
                justification=self.justification.toPlainText(),
            )
            # Re-evaluate both archived snapshots against the current session
            # at preparation time; the history table may have become stale.
            baseline_status = compare_review_source(self.session, baseline)
            candidate_status = compare_review_source(self.session, candidate)
        except (TypeError, ValueError, OverflowError):
            self.summary.setText(self._t("proposal_invalid"))
            return
        self.proposal = proposal
        self.summary.setText(self._t(
            "proposal_result", proposal=proposal.proposal_id,
            status=self._t("proposal_unapproved"),
        ))
        self.source_status.setText(self._t(
            "proposal_source_preflight",
            baseline=self._t(f"record_status.{baseline_status.value}"),
            candidate=self._t(f"record_status.{candidate_status.value}"),
        ))
        # The detached proposal remains visible as an unapproved suggestion,
        # but neither stale nor missing source data may look like clearance.
        if (baseline_status is not ReviewSourceStatus.MATCHING
                or candidate_status is not ReviewSourceStatus.MATCHING):
            self.source_warning.setText(self._t("proposal_source_warning"))
        differences = proposal.comparison.differences
        self.preview.setRowCount(len(differences))
        for row, difference in enumerate(differences):
            for col, value in enumerate((
                self._t(f"comparison_field.{difference.field_name}"),
                difference.first_value, difference.second_value,
            )):
                self.preview.setItem(row, col, QTableWidgetItem(value))
        # Recorded identities are displayed even when values are equal;
        # the differences-only table cannot show such unchanged provenance.
        fields = (
            ("project_id", baseline.project_id, candidate.project_id),
            ("well_id", baseline.source.well_id, candidate.source.well_id),
            ("dataset_id", baseline.source.dataset_id, candidate.source.dataset_id),
            ("depth_axis_id", baseline.source.depth_axis_id, candidate.source.depth_axis_id),
            ("interval_id", baseline.source.interval_id, candidate.source.interval_id),
            ("lithotype_id", baseline.source.lithotype_id, candidate.source.lithotype_id),
            ("top_md_m", baseline.source.top_md_m, candidate.source.top_md_m),
            ("bottom_md_m", baseline.source.bottom_md_m, candidate.source.bottom_md_m),
            ("source_sha256", baseline.source.source_sha256, candidate.source.source_sha256),
            ("axis_sha256", baseline.source.axis_sha256, candidate.source.axis_sha256),
        )
        self.provenance.setRowCount(len(fields))
        for row, (field_name, source_value, candidate_value) in enumerate(fields):
            for col, value in enumerate((
                self._t(f"proposal_provenance_field.{field_name}"),
                str(source_value), str(candidate_value),
            )):
                self.provenance.setItem(row, col, QTableWidgetItem(value))
        self.preview.show()
        self.tabs.show()
