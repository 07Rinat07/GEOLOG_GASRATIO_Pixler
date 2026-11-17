"""Explicit operator preview for exact-row Archie inputs; never a saved Sw curve.

Only verified native GIS data are passed to the isolated computation service.
Free-text operator evidence does not certify geological model applicability.
"""
from __future__ import annotations

from hashlib import sha256
from math import isfinite

import numpy as np
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, QSize, Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSplitter, QTableView, QVBoxLayout, QWidget,
)

from geoworkbench.domain.models import Dataset
from geoworkbench.services.gis_archie_profile import ArchieProfile, ArchieRowStatus
from geoworkbench.services.gis_archie_handoff import (
    ArchieTabletSourceSeal, seal_archie_tablet_source,
)
from geoworkbench.services.gis_archie_source_profile import evaluate_gis_archie_sources
from geoworkbench.services.gis_input_inventory import inventory_gis_inputs
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.gis_reference_profile_track import GisReferenceProfileTrack
from geoworkbench.ui.window_geometry import fit_window_to_screen


_FIELDS = (
    "reviewer", "applicability_reference", "effective_porosity_reference",
    "true_resistivity_reference", "alignment_reference", "water_resistivity_reference",
    "md_top_m", "md_base_m", "formation_water_resistivity_ohm_m", "tortuosity_factor",
    "cementation_exponent", "saturation_exponent",
)
def _live_fingerprint(dataset: Dataset, phi_key: str, rt_key: str) -> tuple[object, ...]:
    """Compare complete live arrays and provenance after the preview modal closes."""
    axis = dataset.active_index
    phi, rt = dataset.curves[phi_key], dataset.curves[rt_key]

    def fingerprint(array: np.ndarray) -> tuple[object, ...]:
        digest = sha256()
        digest.update(array.dtype.str.encode("ascii"))
        digest.update(str(array.shape).encode("ascii"))
        digest.update(np.ascontiguousarray(array).data)
        return (id(array), digest.digest())

    return (
        dataset.kind, dataset.dataset_id, dataset.active_index_id,
        axis.index_id, axis.mnemonic, axis.index_type, axis.role,
        axis.unit, axis.confidence, axis.evidence,
        fingerprint(axis.values), fingerprint(phi.values), fingerprint(rt.values),
        phi.metadata, phi.version, phi.state, rt.metadata, rt.version, rt.state,
        inventory_gis_inputs(dataset),
    )


class _ArchiePreviewModel(QAbstractTableModel):
    """Fixed copied input pairs and output rows; never reads a live curve in data()."""

    def __init__(self, profile: ArchieProfile, source_pairs: tuple[tuple[float, float], ...],
                 localizer: Localizer, parent: QWidget) -> None:
        super().__init__(parent)
        self.profile = profile
        self.source_pairs = source_pairs
        self.localizer = localizer
        self.headers = tuple(localizer.text("petro_reference.archie_" + key) for key in (
            "row", "md", "phi", "rt", "sw", "qc",
        ))

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.profile.rows)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.headers)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self.headers):
                return self.headers[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QModelIndex | QPersistentModelIndex,
             role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if (
            not index.isValid() or not 0 <= index.row() < len(self.profile.rows)
            or not 0 <= index.column() < len(self.headers)
        ):
            return None
        row = self.profile.rows[index.row()]
        if role == Qt.ItemDataRole.ToolTipRole and index.column() == 5:
            return row.issue
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        phi, rt = self.source_pairs[index.row()]
        if index.column() == 0:
            return str(row.sample_index + 1)
        if index.column() == 1:
            return format(row.md_m, ".17g")
        if index.column() in (2, 3):
            value = phi if index.column() == 2 else rt
            return "—" if not isfinite(value) else format(value, ".12g")
        if index.column() == 4:
            return "—" if row.estimate is None else format(row.estimate.value, ".12g")
        if row.status is ArchieRowStatus.ESTIMATED and row.estimate is not None:
            return self.localizer.text("petro_reference." + row.estimate.quality.value)
        return self.localizer.text("petro_reference.archie_" + row.status.value)


class GisArchieProfileDialog(QDialog):
    """Read-only exact measured rows; a snapshot, not an approved reservoir result."""

    def __init__(self, profile: ArchieProfile, source_pairs: tuple[tuple[float, float], ...],
                 *, language: AppLanguage = AppLanguage.RU,
                 parent: QWidget | None = None,
                 allow_tablet_navigation: bool = False) -> None:
        super().__init__(parent)
        self.profile = profile
        self.tablet_row_index: int | None = None
        self._allow_tablet_navigation = allow_tablet_navigation
        self.setObjectName("gis-archie-profile-dialog")
        localizer = Localizer.create(language)
        self.setWindowTitle(localizer.text("petro_reference.archie_title"))
        root = QVBoxLayout(self)
        evidence = QLabel(
            localizer.text("petro_reference.archie_evidence_summary",
                           reviewer=profile.reviewer, method=profile.method_id,
                           phi=profile.porosity_source, rt=profile.resistivity_source,
                           alignment=profile.alignment_reference or "",
                           water=profile.water_resistivity_reference,
                           applicability=profile.applicability_reference),
            self,
        )
        evidence.setTextFormat(Qt.TextFormat.PlainText)
        evidence.setWordWrap(True)
        evidence.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(evidence)
        parameters = profile.coefficients
        self.parameters_label = QLabel(
            localizer.text(
                "petro_reference.archie_parameters",
                rw=format(parameters.formation_water_resistivity_ohm_m, ".12g"),
                a=format(parameters.tortuosity_factor, ".12g"),
                m=format(parameters.cementation_exponent, ".12g"),
                n=format(parameters.saturation_exponent, ".12g"),
            ),
            self,
        )
        self.parameters_label.setObjectName("gis-archie-profile-coefficients")
        self.parameters_label.setTextFormat(Qt.TextFormat.PlainText)
        self.parameters_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.parameters_label)
        notice = QLabel(localizer.text("petro_reference.archie_notice"), self)
        notice.setWordWrap(True)
        root.addWidget(notice)
        self.table = QTableView(self)
        self.table.setObjectName("gis-archie-profile-table")
        self.model = _ArchiePreviewModel(profile, source_pairs, localizer, self.table)
        self.table.setModel(self.model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        # Reuse the read-only exact-row renderer; it neither creates a tablet
        # layout track nor interpolates or clips saturation estimates.
        self.track = GisReferenceProfileTrack(profile, localizer, self)
        self.track.setObjectName("gis-archie-profile-track")
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.track)
        splitter.addWidget(self.table)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([330, 620])
        self.table.selectionModel().currentRowChanged.connect(self._select_track_row)
        root.addWidget(splitter)
        self.show_in_tablet = QPushButton(
            localizer.text("petro_reference.profile_show_tablet"), self,
        )
        self.show_in_tablet.setObjectName("gis-archie-show-in-tablet")
        self.show_in_tablet.setEnabled(False)
        self.show_in_tablet.setVisible(allow_tablet_navigation)
        self.show_in_tablet.clicked.connect(self._request_tablet)
        root.addWidget(self.show_in_tablet)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        close.button(QDialogButtonBox.StandardButton.Close).setText(localizer.text("common.close"))
        close.rejected.connect(self.reject)
        root.addWidget(close)
        fit_window_to_screen(self, preferred=QSize(1020, 660), minimum=QSize(480, 360))

    def _select_track_row(self, current: QModelIndex, _previous: QModelIndex) -> None:
        self.track.select_row(current.row() if current.isValid() else None)
        self.show_in_tablet.setEnabled(
            self._allow_tablet_navigation and self.track.selected_row is not None
        )

    def _request_tablet(self) -> None:
        row = self.track.selected_row
        if not self._allow_tablet_navigation or row is None:
            return
        self.tablet_row_index = row
        self.accept()


class GisArchieDialog(QDialog):
    """Operator selects two actual sources; all coefficients/evidence remain explicit."""

    def __init__(self, dataset: Dataset, parent: QWidget | None = None,
                 *, language: AppLanguage = AppLanguage.RU,
                 allow_tablet_navigation: bool = False) -> None:
        super().__init__(parent)
        self.dataset = dataset
        self._allow_tablet_navigation = allow_tablet_navigation
        self.tablet_request: ArchieTabletSourceSeal | None = None
        self.localizer = Localizer.create(language)
        self.setObjectName("gis-archie-dialog")
        self.setWindowTitle(self._t("title"))
        root = QVBoxLayout(self)
        intro = QLabel(self._t("notice"), self)
        intro.setWordWrap(True)
        root.addWidget(intro)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        body = QWidget(scroll)
        form = QFormLayout(body)
        self.phi = QComboBox(body)
        self.rt = QComboBox(body)
        for selector in (self.phi, self.rt):
            selector.addItem(self.localizer.text("petro_reference.choose"), None)
            for key, curve in dataset.curves.items():
                selector.addItem(f"{key} [{curve.metadata.unit or '?'}]", key)
        form.addRow(self._t("phi_source"), self.phi)
        form.addRow(self._t("rt_source"), self.rt)
        self.fields: dict[str, QLineEdit] = {}
        for key in _FIELDS:
            field = QLineEdit(body)
            field.setObjectName("gis-archie-" + key)
            field.setMaxLength(2000 if key.endswith("reference") else 100)
            form.addRow(self._t(key), field)
            self.fields[key] = field
        scroll.setWidget(body)
        root.addWidget(scroll)
        self.evaluate = QPushButton(self._t("calculate"), self)
        self.evaluate.setObjectName("gis-archie-calculate")
        self.evaluate.clicked.connect(self._evaluate)
        root.addWidget(self.evaluate)
        self.status = QLabel(self)
        self.status.setObjectName("gis-archie-status")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        close.button(QDialogButtonBox.StandardButton.Close).setText(
            self.localizer.text("common.close")
        )
        close.rejected.connect(self.reject)
        root.addWidget(close)
        fit_window_to_screen(self, preferred=QSize(660, 760), minimum=QSize(440, 380))

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text("petro_reference.archie_" + key, **values)

    @staticmethod
    def _number(text: str) -> float:
        """Decimal dot/comma only; no implicit engineering scale conversions."""
        import re

        value = text.strip()
        if not re.fullmatch(r"[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?", value):
            raise ValueError("An explicit decimal number is required")
        return float(value.replace(",", "."))

    def _evaluate(self) -> None:
        self.tablet_request = None
        self.status.clear()
        phi_key, rt_key = self.phi.currentData(), self.rt.currentData()
        if not isinstance(phi_key, str) or not isinstance(rt_key, str):
            self.status.setText(self._t("invalid"))
            return
        try:
            profile = evaluate_gis_archie_sources(
                self.dataset,
                porosity_curve_key=phi_key,
                resistivity_curve_key=rt_key,
                reviewer=self.fields["reviewer"].text(),
                applicability_reference=self.fields["applicability_reference"].text(),
                effective_porosity_reference=self.fields["effective_porosity_reference"].text(),
                true_resistivity_reference=self.fields["true_resistivity_reference"].text(),
                alignment_reference=self.fields["alignment_reference"].text(),
                water_resistivity_reference=self.fields["water_resistivity_reference"].text(),
                md_top_m=self._number(self.fields["md_top_m"].text()),
                md_base_m=self._number(self.fields["md_base_m"].text()),
                formation_water_resistivity_ohm_m=self._number(
                    self.fields["formation_water_resistivity_ohm_m"].text()
                ),
                tortuosity_factor=self._number(self.fields["tortuosity_factor"].text()),
                cementation_exponent=self._number(self.fields["cementation_exponent"].text()),
                saturation_exponent=self._number(self.fields["saturation_exponent"].text()),
            )
            stamp = _live_fingerprint(self.dataset, phi_key, rt_key)
            source_pairs = tuple(
                (
                    float(self.dataset.curves[phi_key].values[row.sample_index]),
                    float(self.dataset.curves[rt_key].values[row.sample_index]),
                )
                for row in profile.rows
            )
        except (ValueError, TypeError, OverflowError, KeyError, IndexError) as error:
            self.status.setText(self._t("invalid") + ": " + str(error))
            return
        draft = (phi_key, rt_key, tuple(field.text() for field in self.fields.values()))
        preview = GisArchieProfileDialog(
            profile, source_pairs, language=self.localizer.language, parent=self,
            allow_tablet_navigation=self._allow_tablet_navigation,
        )
        try:
            accepted = preview.exec() == QDialog.DialogCode.Accepted
            row_to_show = preview.tablet_row_index if accepted else None
        finally:
            preview.deleteLater()
        try:
            if draft != (
                self.phi.currentData(), self.rt.currentData(),
                tuple(field.text() for field in self.fields.values()),
            ) or _live_fingerprint(self.dataset, phi_key, rt_key) != stamp:
                raise ValueError("GIS sources or operator input changed during preview")
        except (ValueError, TypeError, KeyError):
            self.status.setText(self._t("stale"))
            return
        if row_to_show is not None:
            try:
                seal = seal_archie_tablet_source(
                    self.dataset, profile, porosity_curve_key=phi_key,
                    resistivity_curve_key=rt_key, row_index=row_to_show,
                )
            except ValueError:
                self.status.setText(self._t("stale"))
                return
            if not seal.is_current(self.dataset):
                self.status.setText(self._t("stale"))
                return
            self.tablet_request = seal
            self.accept()
            return
        self.status.setText(self._t("snapshot"))
