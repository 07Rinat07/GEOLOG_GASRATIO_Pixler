from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.document_bundle import DocumentBundleScopeKind
from geoworkbench.project.document_bundle_selection import DocumentBundleOutputOption
from geoworkbench.services.localization import AppLanguage, LANGUAGE_NAMES, Localizer
from geoworkbench.ui.window_geometry import fit_window_to_screen


@dataclass(frozen=True, slots=True)
class DocumentBundleDialogSelection:
    outputs: tuple[DocumentBundleOutputOption, ...]
    languages: tuple[str, ...]
    orientations: tuple[str, ...]
    scope_kind: DocumentBundleScopeKind
    top_depth: float | None
    bottom_depth: float | None
    allow_drafts: bool


class DocumentBundleSelectionDialog(QDialog):
    """Responsive selection dialog for the WELL-06 document-bundle command."""

    def __init__(
        self,
        options: tuple[DocumentBundleOutputOption, ...],
        *,
        language: AppLanguage = AppLanguage.RU,
        available_depth_range: tuple[float, float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.options = options
        self.language = language
        self.localizer = Localizer.create(language)
        self.available_depth_range = available_depth_range

        self.setWindowTitle(self._text("document_bundle.title"))
        root = QVBoxLayout(self)

        intro = QLabel(self._text("document_bundle.description"))
        intro.setWordWrap(True)
        root.addWidget(intro)

        outputs_group = QGroupBox(self._text("document_bundle.outputs"))
        outputs_layout = QVBoxLayout(outputs_group)
        self.output_list = QListWidget()
        self.output_list.setObjectName("document-bundle-output-list")
        for option in options:
            item = QListWidgetItem(option.label)
            item.setData(Qt.ItemDataRole.UserRole, option.output_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(
                f"{option.file_format.value.upper()} · {option.dataset_id}"
            )
            self.output_list.addItem(item)
        outputs_layout.addWidget(self.output_list)
        root.addWidget(outputs_group, 1)

        scope_group = QGroupBox(self._text("document_bundle.scope"))
        scope_form = QFormLayout(scope_group)
        self.scope_combo = QComboBox()
        self.scope_combo.addItem(
            self._text("document_bundle.scope_whole"),
            DocumentBundleScopeKind.WHOLE_WELL,
        )
        self.scope_combo.addItem(
            self._text("document_bundle.scope_new_section"),
            DocumentBundleScopeKind.NEW_SECTION,
        )
        self.scope_combo.addItem(
            self._text("document_bundle.scope_interval"),
            DocumentBundleScopeKind.INTERVAL,
        )
        scope_form.addRow(self._text("document_bundle.scope_mode"), self.scope_combo)

        self.top_depth = self._depth_spin()
        self.bottom_depth = self._depth_spin()
        if available_depth_range is not None:
            self.top_depth.setValue(available_depth_range[0])
            self.bottom_depth.setValue(available_depth_range[1])
        scope_form.addRow(self._text("document_bundle.top_depth"), self.top_depth)
        scope_form.addRow(self._text("document_bundle.bottom_depth"), self.bottom_depth)
        root.addWidget(scope_group)

        choices = QHBoxLayout()

        languages_group = QGroupBox(self._text("document_bundle.languages"))
        languages_layout = QVBoxLayout(languages_group)
        self.language_checks: dict[str, QCheckBox] = {}
        for app_language in AppLanguage:
            check = QCheckBox(LANGUAGE_NAMES[app_language])
            check.setChecked(app_language is language)
            check.toggled.connect(self._selection_changed)
            self.language_checks[app_language.value] = check
            languages_layout.addWidget(check)
        choices.addWidget(languages_group)

        orientation_group = QGroupBox(self._text("document_bundle.orientations"))
        orientation_layout = QVBoxLayout(orientation_group)
        self.portrait_check = QCheckBox(self._text("document_bundle.portrait"))
        self.portrait_check.setChecked(True)
        self.portrait_check.toggled.connect(self._selection_changed)
        orientation_layout.addWidget(self.portrait_check)
        self.landscape_check = QCheckBox(self._text("document_bundle.landscape"))
        self.landscape_check.toggled.connect(self._selection_changed)
        orientation_layout.addWidget(self.landscape_check)
        choices.addWidget(orientation_group)

        root.addLayout(choices)

        self.allow_drafts = QCheckBox(self._text("document_bundle.allow_drafts"))
        self.allow_drafts.setToolTip(self._text("document_bundle.allow_drafts_help"))
        root.addWidget(self.allow_drafts)

        self.status_label = QLabel()
        self.status_label.setObjectName("document-bundle-selection-status")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.prepare_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.prepare_button.setText(self._text("document_bundle.prepare"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.output_list.itemChanged.connect(self._selection_changed)
        self.scope_combo.currentIndexChanged.connect(self._scope_changed)
        self.top_depth.valueChanged.connect(self._selection_changed)
        self.bottom_depth.valueChanged.connect(self._selection_changed)

        self._scope_changed()
        self._selection_changed()
        fit_window_to_screen(
            self,
            preferred=QSize(760, 720),
            minimum=QSize(520, 420),
        )

    def selection(self) -> DocumentBundleDialogSelection:
        scope_kind = self._scope_kind()
        explicit_range = scope_kind is not DocumentBundleScopeKind.WHOLE_WELL
        return DocumentBundleDialogSelection(
            outputs=self.selected_outputs(),
            languages=tuple(
                code
                for code, check in self.language_checks.items()
                if check.isChecked()
            ),
            orientations=tuple(
                orientation
                for orientation, checked in (
                    ("portrait", self.portrait_check.isChecked()),
                    ("landscape", self.landscape_check.isChecked()),
                )
                if checked
            ),
            scope_kind=scope_kind,
            top_depth=float(self.top_depth.value()) if explicit_range else None,
            bottom_depth=float(self.bottom_depth.value()) if explicit_range else None,
            allow_drafts=self.allow_drafts.isChecked(),
        )

    def selected_outputs(self) -> tuple[DocumentBundleOutputOption, ...]:
        by_id = {option.output_id: option for option in self.options}
        selected: list[DocumentBundleOutputOption] = []
        for index in range(self.output_list.count()):
            item = self.output_list.item(index)
            if item.checkState() is not Qt.CheckState.Checked:
                continue
            output_id = item.data(Qt.ItemDataRole.UserRole)
            option = by_id.get(output_id)
            if option is not None:
                selected.append(option)
        return tuple(selected)

    def _depth_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(3)
        spin.setRange(-1_000_000_000.0, 1_000_000_000.0)
        spin.setSingleStep(1.0)
        return spin

    def _scope_changed(self) -> None:
        scope_kind = self._scope_kind()
        explicit = scope_kind is not DocumentBundleScopeKind.WHOLE_WELL
        self.top_depth.setEnabled(explicit)
        self.bottom_depth.setEnabled(explicit)
        self._selection_changed()

    def _selection_changed(self) -> None:
        selected_outputs = self.selected_outputs()
        landscape_supported = all(
            "landscape" in option.supported_orientations
            for option in selected_outputs
        )
        self.landscape_check.setEnabled(landscape_supported)
        if not landscape_supported:
            self.landscape_check.setChecked(False)

        has_language = any(check.isChecked() for check in self.language_checks.values())
        has_orientation = (
            self.portrait_check.isChecked() or self.landscape_check.isChecked()
        )
        scope_kind = self._scope_kind()
        range_valid = (
            scope_kind is DocumentBundleScopeKind.WHOLE_WELL
            or self.bottom_depth.value() > self.top_depth.value()
        )
        ready = bool(selected_outputs) and has_language and has_orientation and range_valid
        self.prepare_button.setEnabled(ready)

        if not selected_outputs:
            status = self._text("document_bundle.select_output")
        elif not has_language:
            status = self._text("document_bundle.select_language")
        elif not has_orientation:
            status = self._text("document_bundle.select_orientation")
        elif not range_valid:
            status = self._text("document_bundle.invalid_interval")
        elif not landscape_supported:
            status = self._text("document_bundle.roll_portrait_only")
        else:
            status = self._text("document_bundle.ready")
        self.status_label.setText(status)

    def _scope_kind(self) -> DocumentBundleScopeKind:
        value = self.scope_combo.currentData()
        if isinstance(value, DocumentBundleScopeKind):
            return value
        try:
            return DocumentBundleScopeKind(str(value))
        except ValueError as exc:
            raise RuntimeError("Document bundle scope selection is invalid") from exc

    def _text(self, key: str) -> str:
        return self.localizer.text(key)
