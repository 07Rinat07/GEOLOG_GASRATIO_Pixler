from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt

from geoworkbench.services.depth_axis import DepthDirection
from geoworkbench.services.external_las_insert import (
    ExternalLasCurveCandidate,
    ExternalLasInsertAnalysis,
    ExternalLasMapping,
)
from geoworkbench.ui.external_las_insert_dialog import ExternalLasInsertDialog


class FakeController:
    def analyze_file(self, path: str | Path) -> ExternalLasInsertAnalysis:
        return ExternalLasInsertAnalysis(
            source_path=Path(path),
            source_dataset_id="source",
            target_dataset_id="target",
            source_sha256="a" * 64,
            source_encoding="utf-8",
            source_original_direction=DepthDirection.DESCENDING,
            source_reversed_in_memory=True,
            source_depth_unit="ft",
            target_depth_unit="m",
            depth_conversion_factor=0.3048,
            source_depth_min=100.0,
            source_depth_max=200.0,
            target_depth_min=50.0,
            target_depth_max=250.0,
            overlap_top=100.0,
            overlap_bottom=200.0,
            mapping=ExternalLasMapping.LINEAR_OVERLAP,
            candidates=(
                ExternalLasCurveCandidate(
                    "curve-1",
                    "INCL",
                    "deg",
                    "Inclination",
                    "INCL_EXT",
                    10,
                    2,
                ),
            ),
        )


def test_dialog_loads_candidates_and_returns_edited_selection(qapp, tmp_path: Path) -> None:
    path = tmp_path / "survey.las"
    path.write_text("fake", encoding="utf-8")
    dialog = ExternalLasInsertDialog(FakeController(), initial_path=path)

    assert dialog.analysis is not None
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).checkState() == Qt.CheckState.Checked
    dialog.table.item(0, 4).setText("AZIM_IMPORT")
    dialog.table.item(0, 5).setText("Азимут ствола")

    assert dialog.selections[0].target_mnemonic == "AZIM_IMPORT"
    assert dialog.selections[0].display_name == "Азимут ствола"
    assert dialog.buttons.button(dialog.buttons.StandardButton.Ok).isEnabled()
    assert dialog.issues.count() == 2
