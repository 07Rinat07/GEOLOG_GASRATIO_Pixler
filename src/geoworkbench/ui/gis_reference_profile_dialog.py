"""Read-only value-model view of a calibrated exact-row MD profile."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QPersistentModelIndex, QSize, Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHeaderView, QLabel, QTableView, QVBoxLayout, QWidget,
)

from geoworkbench.services.gis_reference_calibration import CalibratedGisProfile, GisProfileRowStatus
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.window_geometry import fit_window_to_screen


MAX_PROFILE_PREVIEW_ROWS = 10_000


class _ProfileModel(QAbstractTableModel):
    """Python value rows, without native-owned per-cell item wrappers."""

    def __init__(self, profile: CalibratedGisProfile, localizer: Localizer, parent: QObject) -> None:
        super().__init__(parent)
        self.profile = profile
        self.localizer = localizer
        source = profile.calibration.source
        unit = (source.curve.unit if source.curve is not None else None) or source.required_unit
        self.headers = (
            localizer.text("petro_reference.profile_row"),
            localizer.text("petro_reference.profile_md"),
            localizer.text("petro_reference.profile_source", unit=unit),
            localizer.text("petro_reference.profile_estimate"),
            localizer.text("petro_reference.profile_qc"),
        )

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
        if role == Qt.ItemDataRole.ToolTipRole and index.column() == 4:
            return row.issue
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if index.column() == 0:
            return str(row.sample_index + 1)
        if index.column() == 1:
            return format(row.md_m, ".17g")
        if index.column() == 2:
            return "—" if row.source_value is None else format(row.source_value, ".17g")
        if index.column() == 3:
            return "—" if row.estimate is None else format(row.estimate.value, ".12g")
        if row.status is GisProfileRowStatus.ESTIMATED and row.estimate is not None:
            return self.localizer.text("petro_reference." + row.estimate.quality.value)
        return self.localizer.text("petro_reference.profile_" + row.status.value)

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class GisReferenceProfileDialog(QDialog):
    def __init__(self, profile: CalibratedGisProfile, parent: QWidget | None = None,
                 *, language: AppLanguage = AppLanguage.RU) -> None:
        super().__init__(parent)
        self.profile = profile
        self.localizer = Localizer.create(language)
        self.setObjectName("gis-reference-profile-dialog")
        self.setWindowTitle(self.localizer.text("petro_reference.calculate_profile"))
        layout = QVBoxLayout(self)
        calibration = profile.calibration
        source = calibration.source
        context = QLabel(self.localizer.text(
            "petro_reference.profile_context", method=source.method_id, curve=source.curve_key,
            calibration=calibration.calibration_id, top=format(profile.md_bounds[0], ".17g"),
            base=format(profile.md_bounds[1], ".17g"),
        ), self)
        context.setTextFormat(Qt.TextFormat.PlainText)
        context.setWordWrap(True)
        context.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(context)
        notice = QLabel(self.localizer.text("petro_reference.profile_notice"), self)
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.summary = QLabel(self.localizer.text(
            "petro_reference.profile_summary", total=profile.sample_count,
            estimated=profile.estimated_count, missing=profile.missing_count,
            invalid=profile.invalid_count,
        ), self)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.table = QTableView(self)
        self.table.setObjectName("gis-reference-profile-table")
        self.model = _ProfileModel(profile, self.localizer, self.table)
        self.table.setModel(self.model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self.localizer.text("common.close"))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        fit_window_to_screen(self, preferred=QSize(960, 600), minimum=QSize(420, 360))
