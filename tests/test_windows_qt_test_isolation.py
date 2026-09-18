from __future__ import annotations

from pathlib import Path
import runpy

import pytest


def test_masterlog_curve_mapping_dialog_uses_its_own_native_process() -> None:
    runner = runpy.run_path("scripts/run_tests.py")
    path = Path("tests/test_masterlog_curve_mapping_dialog.py")
    nodes = runner["_top_level_test_nodes"](path)

    assert nodes == (
        "tests/test_masterlog_curve_mapping_dialog.py::"
        "test_masterlog_curve_mapping_dialog_maps_foreign_las_curves",
    )
    assert runner["_requires_native_batch"](path, nodes) is True
    assert path.as_posix() in runner["_SINGLE_TEST_PROCESS_FILES"]


def test_native_isolation_keeps_masterlog_mapping_out_of_regular_shards() -> None:
    runner = runpy.run_path("scripts/run_tests.py")
    path = Path("tests/test_masterlog_curve_mapping_dialog.py")

    shards = runner["_test_file_shards"](1, (path,))
    batches = runner["_heavy_test_batches"]((path,))

    assert shards == ()
    assert batches == (
        (
            path.as_posix(),
            (
                "tests/test_masterlog_curve_mapping_dialog.py::"
                "test_masterlog_curve_mapping_dialog_maps_foreign_las_curves",
            ),
        ),
    )



@pytest.mark.parametrize(
    "relative_path",
    (
        "tests/test_daily_las_growth_autosave.py",
        "tests/test_multipage_unicode_print.py",
    ),
)
def test_pyqtgraph_heavy_files_use_fresh_process_per_test(relative_path: str) -> None:
    runner = runpy.run_path("scripts/run_tests.py")
    path = Path(relative_path)
    nodes = runner["_top_level_test_nodes"](path)

    assert nodes
    assert runner["_requires_native_batch"](path, nodes) is True
    assert path.as_posix() in runner["_SINGLE_TEST_PROCESS_FILES"]
    assert runner["_test_file_shards"](1, (path,)) == ()

    batches = runner["_heavy_test_batches"]((path,))
    assert len(batches) == len(nodes)
    assert all(batch_path == path.as_posix() for batch_path, _selectors in batches)
    assert all(len(selectors) == 1 for _batch_path, selectors in batches)
