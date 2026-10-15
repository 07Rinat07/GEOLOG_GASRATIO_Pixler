from pathlib import Path

import numpy as np

from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.import_jobs import ImportSourceKind
from geoworkbench.ui.main_window import MainWindow
from tools.fetch_external_format_fixtures import CORPUS


def test_explicit_pilot_action_loads_real_source_through_review(qapp, monkeypatch) -> None:
    source = CORPUS / "las/3.0/sample_3.0.las"
    original = source.read_bytes()
    window = MainWindow()
    reviewed = []
    monkeypatch.setattr("geoworkbench.ui.main_window.QFileDialog.getOpenFileName",
                        lambda *args, **kwargs: (str(source), "LAS"))
    monkeypatch.setattr(window, "_confirm_las_review", lambda *args: True)
    monkeypatch.setattr("geoworkbench.ui.main_window.QMessageBox.warning", lambda *args: None)
    def review(dataset, kind, path):
        reviewed.append((kind, path))
        return dataset
    monkeypatch.setattr(window, "_review_imported_dataset", review)
    try:
        window.open_las3_pilot_action.trigger()
        dataset = window.session.current_dataset
        assert dataset is not None
        assert reviewed == [(ImportSourceKind.LAS, Path(source))]
        np.testing.assert_array_equal(dataset.depth, [1670.0, 1669.875, 1669.75])
        assert window.session.source_documents[dataset.dataset_id].to_bytes() == original
        assert dataset.version_headers["VERS"] == "3.0"
        # Switching localization must preserve live native plot ownership:
        # Windows offscreen pyqtgraph can crash during synchronous rebuilds.
        existing = {
            track_id: entry.plot
            for track_id, entry in window.tablet_view._rendered.items()
        }
        assert existing
        for language in AppLanguage:
            window.change_language(language)
            assert window.open_las3_pilot_action.text() == window._t("import.las3_pilot")
            assert {
                track_id: entry.plot
                for track_id, entry in window.tablet_view._rendered.items()
            } == existing
            assert all(
                entry.widget.title.text()
                for entry in window.tablet_view._rendered.values()
            )
        assert source.read_bytes() == original
    finally:
        window.close()
