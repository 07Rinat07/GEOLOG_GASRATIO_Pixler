from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW = ROOT / "src/geoworkbench/ui/main_window.py"
I18N_ROOT = ROOT / "src/geoworkbench/resources/i18n"


def test_main_window_exposes_document_bundle_command_through_application_boundary() -> None:
    source = MAIN_WINDOW.read_text(encoding="utf-8")

    assert "DocumentBundleCommandController" in source
    assert "DocumentBundleSelectionDialog" in source
    assert 'self.document_bundle_action = self._localized_action("document_bundle.action")' in source
    assert "self.document_bundle_action.triggered.connect(self.prepare_document_bundle)" in source
    assert (
        'self.retry_document_bundle_action = self._localized_action(\n'
        '            "document_bundle.retry_failed"\n'
        "        )"
    ) in source
    assert "self.retry_document_bundle_action.setEnabled(False)" in source
    assert "self.retry_document_bundle_action.triggered.connect(" in source
    assert "self.retry_document_bundle_action.setEnabled(" in source
    assert "file_menu.addAction(self.document_bundle_action)" in source
    assert "print_menu.addAction(self.document_bundle_action)" in source
    assert "file_menu.addAction(self.retry_document_bundle_action)" in source
    assert "print_menu.addAction(self.retry_document_bundle_action)" in source
    assert "command.execute(" in source
    assert "command.retry_failed(previous)" in source
    assert source.count("self._remember_document_bundle_execution(None)") >= 3


def test_main_window_keeps_document_bundle_runtime_behind_command_controller() -> None:
    source = MAIN_WINDOW.read_text(encoding="utf-8")
    method = source.split("    def prepare_document_bundle", 1)[1].split(
        "    def show_well_passport", 1
    )[0]

    assert "build_document_bundle_runtime" not in source
    assert "DocumentBundleSnapshotController" not in method
    assert "DefaultDocumentBundleExporterFactory" not in method
    assert "DocumentBundleApplicationService" not in method


def test_document_bundle_main_window_strings_are_localized() -> None:
    required_keys = {
        "document_bundle.action",
        "document_bundle.retry_failed",
        "document_bundle.output_directory_title",
        "document_bundle.failed",
        "document_bundle.complete",
        "document_bundle.partial",
        "document_bundle.status_complete",
        "document_bundle.status_partial",
        "document_bundle.retry_not_required",
    }

    for language in ("ru", "kk", "en"):
        data = json.loads((I18N_ROOT / f"{language}.json").read_text(encoding="utf-8"))
        missing = required_keys.difference(data)
        assert not missing, f"{language} is missing {sorted(missing)}"
