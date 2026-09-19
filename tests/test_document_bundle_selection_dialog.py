from __future__ import annotations

from PySide6.QtCore import Qt

from geoworkbench.domain.document_bundle import (
    DocumentBundleOutputFormat,
    DocumentBundleScopeKind,
)
from geoworkbench.project.document_bundle_selection import (
    DocumentBundleOutputOption,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.document_bundle_selection_dialog import (
    DocumentBundleSelectionDialog,
)


def _options() -> tuple[DocumentBundleOutputOption, ...]:
    return (
        DocumentBundleOutputOption(
            output_id="masterlog:a4:dataset-1",
            label="A4 Gas Log",
            exporter_kind="masterlog",
            source_id="a4",
            dataset_id="dataset-1",
            file_format=DocumentBundleOutputFormat.PDF,
            target_name="a4-gas-log.pdf",
            supported_orientations=("portrait", "landscape"),
        ),
        DocumentBundleOutputOption(
            output_id="masterlog:roll:dataset-1",
            label="Roll Field Log",
            exporter_kind="masterlog",
            source_id="roll",
            dataset_id="dataset-1",
            file_format=DocumentBundleOutputFormat.PDF,
            target_name="roll-field-log.pdf",
            supported_orientations=("portrait",),
        ),
    )


def _check_output(dialog: DocumentBundleSelectionDialog, index: int) -> None:
    dialog.output_list.item(index).setCheckState(Qt.CheckState.Checked)


def test_document_bundle_dialog_fits_current_work_area(qapp) -> None:
    dialog = DocumentBundleSelectionDialog(
        _options(),
        language=AppLanguage.EN,
        available_depth_range=(1000.0, 1100.0),
    )
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()
    finally:
        dialog.close()


def test_prepare_is_enabled_only_after_valid_output_selection(qapp) -> None:
    dialog = DocumentBundleSelectionDialog(
        _options(),
        language=AppLanguage.EN,
        available_depth_range=(1000.0, 1100.0),
    )
    try:
        assert dialog.prepare_button.isEnabled() is False

        _check_output(dialog, 0)

        assert dialog.prepare_button.isEnabled() is True
        selection = dialog.selection()
        assert [item.source_id for item in selection.outputs] == ["a4"]
        assert selection.languages == ("en",)
        assert selection.orientations == ("portrait",)
        assert selection.scope_kind is DocumentBundleScopeKind.WHOLE_WELL
        assert selection.top_depth is None
        assert selection.bottom_depth is None
    finally:
        dialog.close()


def test_roll_output_disables_and_clears_landscape(qapp) -> None:
    dialog = DocumentBundleSelectionDialog(
        _options(),
        language=AppLanguage.EN,
        available_depth_range=(1000.0, 1100.0),
    )
    try:
        _check_output(dialog, 0)
        dialog.landscape_check.setChecked(True)
        assert dialog.landscape_check.isChecked() is True

        _check_output(dialog, 1)

        assert dialog.landscape_check.isEnabled() is False
        assert dialog.landscape_check.isChecked() is False
        assert dialog.selection().orientations == ("portrait",)
    finally:
        dialog.close()


def test_interval_selection_returns_explicit_bounds_and_draft_policy(qapp) -> None:
    dialog = DocumentBundleSelectionDialog(
        _options(),
        language=AppLanguage.RU,
        available_depth_range=(1000.0, 1100.0),
    )
    try:
        _check_output(dialog, 0)
        interval_index = dialog.scope_combo.findData(DocumentBundleScopeKind.INTERVAL)
        assert interval_index >= 0
        dialog.scope_combo.setCurrentIndex(interval_index)
        dialog.top_depth.setValue(1025.0)
        dialog.bottom_depth.setValue(1085.0)
        dialog.language_checks["kk"].setChecked(True)
        dialog.allow_drafts.setChecked(True)

        selection = dialog.selection()

        assert selection.scope_kind is DocumentBundleScopeKind.INTERVAL
        assert selection.top_depth == 1025.0
        assert selection.bottom_depth == 1085.0
        assert selection.languages == ("ru", "kk")
        assert selection.allow_drafts is True
        assert dialog.prepare_button.isEnabled() is True
    finally:
        dialog.close()


def test_invalid_interval_disables_prepare(qapp) -> None:
    dialog = DocumentBundleSelectionDialog(
        _options(),
        language=AppLanguage.EN,
        available_depth_range=(1000.0, 1100.0),
    )
    try:
        _check_output(dialog, 0)
        interval_index = dialog.scope_combo.findData(DocumentBundleScopeKind.INTERVAL)
        dialog.scope_combo.setCurrentIndex(interval_index)
        dialog.top_depth.setValue(1080.0)
        dialog.bottom_depth.setValue(1070.0)

        assert dialog.prepare_button.isEnabled() is False
    finally:
        dialog.close()
