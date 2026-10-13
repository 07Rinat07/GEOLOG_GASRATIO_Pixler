"""Actual Qt tablet geometry acceptance on pinned LAS 3.0 scalar pilot source.

The fixture uses an explicit, limited LAS 3.0 importer. This verifies its
eight numeric channels can be plotted, and plotted again after real JSON/package
project reopen. It does not authorize general LAS 3.x or source write-back.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from geoworkbench.data.las3_dataset_adapter import import_las3_scalar_dataset
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView
from tools.fetch_external_format_fixtures import CORPUS


_SOURCE = CORPUS / "las/3.0/sample_3.0.las"


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("extension", [".geolog.json", ".geologpkg"])
def test_las3_scalar_tablet_displays_true_data_after_project_reopen(
    qapp, tmp_path: Path, language: AppLanguage, extension: str,
) -> None:
    original = _SOURCE.read_bytes()
    result = import_las3_scalar_dataset(_SOURCE)
    session = ProjectSession()
    session.add_dataset(
        result.dataset,
        source_document=result.source_document,
        import_report=result.report,
        create_new_well=True,
    )
    destination = tmp_path / ("las3-scalar-tablet" + extension)
    ProjectController(session=session).save_project(destination)

    reopened = ProjectController().open_project(destination)
    dataset = reopened.current_dataset
    assert dataset is not None
    assert reopened.source_documents[dataset.dataset_id].to_bytes() == original
    assert reopened.import_reports[dataset.dataset_id].source.sha256 == result.report.source.sha256
    assert reopened.dirty is False

    layout = TabletLayout(
        [
            TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=90),
            TrackDefinition("sonic", "Sonic DT", TrackKind.CURVE,
                            curve_mnemonics=["DT"], width=280),
            TrackDefinition("resistivity", "Deep resistivity", TrackKind.CURVE,
                            curve_mnemonics=["ILD"], width=280),
        ],
        vertical_index_id=dataset.active_index.index_id,
        visible_depth_top=1669.7,
        visible_depth_bottom=1670.05,
    )
    view = TabletView(language=language)
    try:
        view.resize(900, 640)
        view.show()
        view.set_layout_and_dataset(layout, dataset)
        qapp.processEvents()
        view.set_visible_depth(1669.7, 1670.05)
        qapp.processEvents()

        for track_id, mnemonic, expected in (
            ("sonic", "DT", [123.45, 123.45, 123.45]),
            ("resistivity", "ILD", [105.6, 105.6, 105.6]),
        ):
            curve = dataset.curve_by_mnemonic(mnemonic)
            assert curve is not None
            assert view.rendered_curve_point_count(track_id, mnemonic) == 3
            item = view._rendered[track_id].curve_items[mnemonic]
            x_values, y_values = item.getData()
            np.testing.assert_allclose(x_values, expected, rtol=0, atol=1e-6)
            np.testing.assert_allclose(
                y_values, dataset.depth, rtol=0, atol=1e-6
            )
            np.testing.assert_allclose(
                curve.values, expected, rtol=0, atol=1e-6
            )
            assert curve.metadata.unit == ("US/M" if mnemonic == "DT" else "OHMM")
            assert item.opts.get("pen") is not None

            # The existing print presentation must not alter the actual
            # screen curve geometry or persisted source measurements.
            widget = view._rendered[track_id].widget
            widget.set_print_mode(True)
            px, py = item.getData()
            np.testing.assert_allclose(px, x_values)
            np.testing.assert_allclose(py, y_values)
            widget.set_print_mode(False)

        assert "CDES" not in view._rendered["sonic"].curve_items
        assert "NMR[1]" not in view._rendered["resistivity"].curve_items
        assert reopened.current_dataset is dataset
        assert _SOURCE.read_bytes() == original
    finally:
        view.close()
