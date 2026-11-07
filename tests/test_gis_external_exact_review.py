from dataclasses import replace
import json

import numpy as np
import pytest

from geoworkbench.domain.models import CurveData, CurveMetadata, DatasetKind
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.external_las_insert_controller import ExternalLasInsertController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.external_las_insert import ExternalLasCurveSelection
from geoworkbench.services.gis_input_inventory import exact_external_gis_curve_ids, inventory_gis_inputs
from geoworkbench.services.gis_interval_sample_review import review_gis_interval_samples
from geoworkbench.services.gis_reference_input_review import review_gis_reference_input
from geoworkbench.services.semantic_channels import SemanticChannelDictionary
from geoworkbench.ui.gis_reference_dialog import GisReferenceDialog
from test_external_las_insert_controller import dataset, imported


def _copy(monkeypatch, tmp_path, *, source_depth=(100.0, 101.0, 102.0), target_name="GR"):
    receiver = dataset("gas", [100.0, 101.0, 102.0])
    source = dataset("gis", list(source_depth))
    source.kind = DatasetKind.GIS
    binding = SemanticChannelDictionary().resolve("GR", unit="API")
    source.curves["gr"] = CurveData(
        CurveMetadata("gr", "GR", binding.canonical_mnemonic, "API", "Gamma",
                      source.dataset_id, "source:las", binding),
        np.arange(len(source_depth), dtype=float),
    )
    session = ProjectSession()
    session.add_dataset(receiver)
    controller = ExternalLasInsertController(session)
    monkeypatch.setattr(
        "geoworkbench.project.external_las_insert_controller.import_las_with_report",
        lambda _path: imported(source, tmp_path / "gis.las"),
    )
    analysis = controller.analyze_file(tmp_path / "gis.las")
    result = controller.create_copy(analysis, (ExternalLasCurveSelection("gr", target_name),))
    return session, receiver, source, result.dataset


@pytest.mark.parametrize("extension", [".geolog.json", ".geologpkg"])
def test_exact_inserted_gis_can_be_reviewed_after_project_reopen(monkeypatch, tmp_path, extension):
    session, receiver, source, combined = _copy(monkeypatch, tmp_path)
    curve = combined.curve_by_mnemonic("GR")
    assert curve is not None and curve.metadata.semantic == source.curves["gr"].metadata.semantic
    assert curve.metadata.curve_id in exact_external_gis_curve_ids(combined)
    key = next(key for key, value in combined.curves.items() if value is curve)
    assert review_gis_reference_input(combined, method_id="igr-linear-1", curve_key=key).ready_for_calibration
    assert review_gis_interval_samples(combined, method_id="igr-linear-1", curve_key=key,
                                       top_md_m=100, bottom_md_m=102).finite_count == 3
    assert receiver.curves == {}
    path = tmp_path / ("project" + extension)
    ProjectController(session=session).save_project(path)
    reopened = ProjectController().open_project(path)
    reopened.current_dataset_id = combined.dataset_id
    restored = reopened.current_dataset
    assert restored is not None
    assert review_gis_reference_input(restored, method_id="igr-linear-1", curve_key=key).ready_for_calibration


def test_interpolated_or_renamed_sources_are_not_silently_accepted(monkeypatch, tmp_path):
    _, _, _, interpolated = _copy(monkeypatch, tmp_path, source_depth=(100.0, 102.0))
    assert not exact_external_gis_curve_ids(interpolated)
    assert "dataset_not_gis" in inventory_gis_inputs(interpolated).axis_issues
    _, _, _, renamed = _copy(monkeypatch, tmp_path, target_name="GR_EXT")
    key = next(iter(renamed.curves))
    review = review_gis_reference_input(renamed, method_id="igr-linear-1", curve_key=key)
    assert "curve:semantic_mnemonic_changed" in review.issues


@pytest.mark.parametrize("change", ["digest", "mapping", "target", "duplicate"])
def test_manifest_tampering_or_ambiguous_curve_ids_block_review(monkeypatch, tmp_path, change):
    _, _, _, combined = _copy(monkeypatch, tmp_path)
    key = next(iter(combined.curves))
    manifest_key = next(key for key in combined.parameters if key.startswith("EXTERNAL_LAS_IMPORT_"))
    manifest = json.loads(combined.parameters[manifest_key])
    if change == "digest":
        manifest["source_sha256"] = "0" * 64
    elif change == "mapping":
        manifest["mapping"] = "linear_overlap"
    elif change == "target":
        manifest["curves"][0]["target_mnemonic"] = "different"
    else:
        combined.curves["duplicate"] = replace(combined.curves[key])
    combined.parameters[manifest_key] = json.dumps(manifest)
    assert not exact_external_gis_curve_ids(combined)
    assert not review_gis_reference_input(combined, method_id="igr-linear-1", curve_key=key).ready_for_calibration


def test_other_curves_in_combined_dataset_do_not_inherit_external_approval(monkeypatch, tmp_path):
    _, _, _, combined = _copy(monkeypatch, tmp_path)
    original = next(iter(combined.curves.values()))
    combined.curves["other"] = CurveData(
        replace(original.metadata, curve_id="other", provenance="source"), original.values.copy(),
    )
    review = review_gis_reference_input(combined, method_id="igr-linear-1", curve_key="other")
    assert "curve:external_source_unverified" in review.issues
    assert not review.ready_for_calibration


def test_duplicate_manifest_fields_do_not_authorize_source(monkeypatch, tmp_path):
    _, _, _, combined = _copy(monkeypatch, tmp_path)
    manifest_key = next(key for key in combined.parameters if key.startswith("EXTERNAL_LAS_IMPORT_"))
    original = combined.parameters[manifest_key]
    combined.parameters[manifest_key] = original.replace('"version": 1', '"version": 1, "version": 1')
    assert combined.parameters[manifest_key] != original
    assert not exact_external_gis_curve_ids(combined)


@pytest.mark.parametrize("reason", ["interpolated", "missing_semantics"])
def test_unverified_copy_explains_review_rejection_in_each_language(qapp, monkeypatch, tmp_path, reason):
    from PySide6.QtWidgets import QMessageBox
    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.main_window import MainWindow

    depths = (100.0, 102.0) if reason == "interpolated" else (100.0, 101.0, 102.0)
    session, receiver, _, combined = _copy(monkeypatch, tmp_path, source_depth=depths)
    if reason == "missing_semantics":
        curve = next(iter(combined.curves.values()))
        curve.metadata = replace(curve.metadata, semantic=None)
    window = MainWindow()
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args[2]))
    monkeypatch.setattr(GisReferenceDialog, "exec", lambda _dialog: pytest.fail("unexpected review"))
    try:
        window.session.project = session.project
        window.session.current_well_id = session.current_well_id
        window.session.current_dataset_id = combined.dataset_id
        window.session.dirty = False
        for language in AppLanguage:
            window.change_language(language)
            window.show_gis_reference_dialog()
            assert messages[-1] == window._t("petro_reference.external_unavailable")
        assert len(messages) == 3
        assert not window.session.dirty
        assert receiver.curves == {}
    finally:
        window.close()


def test_combined_dataset_is_available_from_main_window(qapp, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QDialog
    from geoworkbench.ui.main_window import MainWindow

    session, _, _, combined = _copy(monkeypatch, tmp_path)
    window = MainWindow()
    try:
        window.session.project = session.project
        window.session.current_well_id = session.current_well_id
        window.session.current_dataset_id = combined.dataset_id
        seen = []

        def show(dialog):
            seen.append(dialog.dataset)
            dialog.method.setCurrentIndex(1)
            dialog.channel.setCurrentIndex(dialog.channel.findData(next(iter(combined.curves))))
            dialog.fields["top"].setText("100")
            dialog.fields["base"].setText("102")
            dialog.review_interval.click()
            assert dialog.interval_review_label.text() == (
                dialog._t("interval_summary", total=3, finite=3, missing=0) + "\n"
                + dialog._t("interval_value_bounds", minimum="0", maximum="2", unit="API")
            )
            return QDialog.DialogCode.Rejected

        monkeypatch.setattr(GisReferenceDialog, "exec", show)
        window.show_gis_reference_dialog()
        assert seen == [combined]
    finally:
        window.close()
