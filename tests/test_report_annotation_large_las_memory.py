from hashlib import sha256
from pathlib import Path
import sys
import tracemalloc

import pytest

from benchmarks.benchmark_las_tablet_pipeline import _write_fixture
from geoworkbench.data.las_adapter import import_las
from geoworkbench.domain.models import Project, Well
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.edit_history import CommandHistory
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.process_metrics import process_memory_snapshot
from geoworkbench.ui.interpretation_report_annotation_dialog import InterpretationReportAnnotationDialog


MIB = 1024 * 1024


@pytest.mark.parametrize("rows", (100_000, 1_000_000))
def test_large_las_annotation_editor_history_does_not_copy_source(
    qapp, tmp_path: Path, rows: int, record_property,
) -> None:
    source = tmp_path / "large.las"
    _write_fixture(source, rows=rows, curves=8)
    dataset = import_las(source)
    assert len(dataset.depth) == rows
    assert len(dataset.curves) == 8
    well = Well("large-well", "Large LAS", {dataset.dataset_id: dataset})
    session = ProjectSession(
        Project("large-project", "Memory acceptance", wells={well.well_id: well}),
        well.well_id, dataset.dataset_id,
    )
    arrays = (dataset.depth, *(curve.values for curve in dataset.curves.values()))
    hashes = tuple(sha256(array.data).digest() for array in arrays)
    history = CommandHistory(max_commands=100)
    before = process_memory_snapshot()
    if sys.platform == "win32":
        assert before.rss_bytes is not None, "Windows memory acceptance requires RSS"
    rss_samples = []

    def sample_rss():
        current = process_memory_snapshot().rss_bytes
        if before.rss_bytes is not None and current is not None:
            rss_samples.append(current)

    # Import and source hashing are outside the measured editor transaction.
    # The Python peak catches transient array copies; RSS also covers native Qt.
    tracemalloc.start()
    dialog = None
    try:
        dialog = InterpretationReportAnnotationDialog(
            session, language=AppLanguage.EN, shared_history=history,
        )
        sample_rss()
        assert dialog.controller.shared_history is history
        for index in range(20):
            dialog.annotation.setCurrentIndex(0)
            dialog.track.setCurrentText("curve:C0001")
            dialog.depth_spin.setValue(1.0 + index * 0.1)
            dialog.text.setText(f"Large LAS note {index}")
            dialog.add_button.click()
            assert len(dialog.controller.available()) == index + 1
            sample_rss()
        records = dialog.controller.available()
        for remaining in range(19, -1, -1):
            dialog.undo_button.click()
            assert dialog.controller.available() == records[:remaining]
            sample_rss()
        for restored in range(1, 21):
            dialog.redo_button.click()
            assert dialog.controller.available() == records[:restored]
            sample_rss()
        dialog.reject()
        assert dialog.controller.available() == ()
        assert not session.dirty
        assert not history.can_undo
        assert not history.can_redo
        sample_rss()
        _, python_peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        if dialog is not None:
            dialog.deleteLater()
        qapp.processEvents()

    assert session.current_dataset is dataset
    assert dataset.depth is arrays[0]
    for curve, array in zip(dataset.curves.values(), arrays[1:], strict=True):
        assert curve.values is array
    assert tuple(sha256(array.data).digest() for array in arrays) == hashes
    assert not session.report_compositions
    record_property("rows", rows)
    record_property("editor_python_peak_bytes", python_peak)
    # One million float64 samples occupy 8 MiB per array: even one transient
    # source copy exceeds this row-count-independent editor allocation budget.
    assert python_peak < 4 * MIB
    if rss_samples:
        growth = max(0, max(rss_samples) - before.rss_bytes)
        record_property("editor_rss_growth_bytes", growth)
        assert growth < 32 * MIB
        print(f"rows={rows}, Python peak={python_peak / MIB:.2f} MiB, RSS growth={growth / MIB:.2f} MiB")
