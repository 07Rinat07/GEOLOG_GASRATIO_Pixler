import numpy as np
import pytest

from geoworkbench.data.las_adapter import import_las_with_report
from geoworkbench.domain.models import DatasetKind
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.gis_reference_dialog import GisReferenceDialog
from tools.fetch_external_format_fixtures import CORPUS


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("extension", [".geolog.json", ".geologpkg"])
def test_imported_wrapped_las_reference_survives_project_reopen(
    qapp, tmp_path, language, extension,
):
    source = CORPUS / "las/2.0/sample_2.0_wrapped.las"
    original_bytes = source.read_bytes()
    imported = import_las_with_report(source, DatasetKind.GIS)
    dataset = imported.dataset
    depths = dataset.active_index.values.copy()
    values = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    metadata = {key: curve.metadata for key, curve in dataset.curves.items()}
    gr_key = next(key for key, curve in dataset.curves.items()
                  if curve.metadata.original_mnemonic == "GR")
    density_key = next(key for key, curve in dataset.curves.items()
                       if curve.metadata.original_mnemonic == "RHOB")
    # Independent values from the wrapped LAS rows, not a second call to the calculator.
    np.testing.assert_array_equal(depths, [910.0, 909.875])
    np.testing.assert_allclose(values[gr_key], [96.5306, 90.2803])
    session = ProjectSession()
    session.add_dataset(dataset, source_document=imported.source_document,
                        import_report=imported.report)
    project = tmp_path / ("gis-reference" + extension)
    ProjectController(session=session).save_project(project)
    project_bytes = project.read_bytes()
    reopened = ProjectController().open_project(project)
    results = []
    for current in (session, reopened):
        restored = current.current_dataset
        assert restored is not None and not current.dirty
        dialog = GisReferenceDialog(restored, language=language)
        try:
            assert dialog.sample is None
            assert all(not field.text() for field in dialog.fields.values())
            assert not dialog.source_sample_label.text()
            dialog.method.setCurrentIndex(1)
            dialog.channel.setCurrentIndex(dialog.channel.findData(gr_key))
            dialog.row.setValue(2)
            dialog.review_source.click()
            assert dialog.source_review_label.text() == dialog._t("source_ready")
            assert dialog.source_sample_label.text() == dialog._t(
                "source_sample", row=2, md="909.875", value="90.2803",
                unit=metadata[gr_key].unit,
            )
            for key, value in dict(
                calibration_id="fixture-cal", tool_id="fixture-tool", reviewer="Test reviewer",
                evidence="Synthetic calibration only; not field acceptance",
                top="909.875", base="910",
            ).items():
                dialog.fields[key].setText(value)
            for field, value in zip(dialog.parameters, ("25", "125")):
                field.setText(value)
            dialog.calculate.click()
            sample = dialog.sample
            assert sample is not None
            assert sample.sample_index == 1 and sample.md_m == 909.875
            assert sample.source_value == pytest.approx(90.2803)
            assert sample.estimate.value == pytest.approx(0.652803)
            assert sample.calibration.source.curve.curve_id == metadata[gr_key].curve_id
            assert sample.calibration.source.curve.source_dataset_id == (
                metadata[gr_key].source_dataset_id
            )
            results.append(sample.estimate.value)
            # The corpus density unit must remain unsupported, including after persistence.
            dialog.method.setCurrentIndex(2)
            dialog.channel.setCurrentIndex(dialog.channel.findData(density_key))
            dialog.review_source.click()
            assert dialog.localizer.text("gis_inventory.issue.unknown_unit") in (
                dialog.source_review_label.text()
            )
            assert dialog.sample is None and not dialog.source_sample_label.text()
        finally:
            dialog.close()
        assert not current.dirty
        np.testing.assert_array_equal(restored.active_index.values, depths)
        for key, expected in values.items():
            np.testing.assert_array_equal(restored.curves[key].values, expected)
            assert restored.curves[key].metadata == metadata[key]
        assert current.source_documents[restored.dataset_id].to_bytes() == original_bytes
    assert results[0] == results[1]
    assert source.read_bytes() == original_bytes
    assert project.read_bytes() == project_bytes
