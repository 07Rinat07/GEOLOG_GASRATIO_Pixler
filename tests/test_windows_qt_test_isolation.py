from __future__ import annotations

from pathlib import Path
import runpy

import pytest

from geoworkbench.services.localization import AppLanguage


def test_masterlog_curve_mapping_dialog_uses_its_own_native_process() -> None:
    runner = runpy.run_path("scripts/run_tests.py")
    path = Path("tests/test_masterlog_curve_mapping_dialog.py")
    nodes = runner["_top_level_test_nodes"](path)

    assert nodes == (
        "tests/test_masterlog_curve_mapping_dialog.py::"
        "test_masterlog_curve_mapping_dialog_maps_foreign_las_curves",
        "tests/test_masterlog_curve_mapping_dialog.py::"
        "test_masterlog_curve_mapping_dialog_scrolls_fields_above_actions",
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
        (
            path.as_posix(),
            (
                "tests/test_masterlog_curve_mapping_dialog.py::"
                "test_masterlog_curve_mapping_dialog_scrolls_fields_above_actions",
            ),
        ),
    )



@pytest.mark.parametrize(
    "relative_path",
    (
        "tests/test_adaptive_geology_dialogs.py",
        "tests/test_daily_las_growth_autosave.py",
        "tests/test_gis_archie_tablet_handoff.py",
        "tests/test_gis_profile_tablet_navigation.py",
        "tests/test_lithology_drag_editor.py",
        "tests/test_lithology_mapping_dialog.py",
        "tests/test_localization.py",
        "tests/test_report_document_control_docx_footer.py",
        "tests/test_multipage_unicode_print.py",
        "tests/test_well_update_workflow.py",
        "tests/test_widget_print.py",
        "tests/test_wits0_capture.py",
        "tests/test_wits0_capture_dialog.py",
        "tests/test_wits0_live_view.py",
        "tests/test_wits0_network_preflight.py",
        "tests/test_wits0_operator_dashboard.py",
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
    assert tuple(selector for _batch_path, selectors in batches for selector in selectors) == nodes


def test_archie_stale_seal_cases_use_separate_native_processes() -> None:
    runner = runpy.run_path("scripts/run_tests.py")
    path = Path("tests/test_gis_archie_tablet_handoff.py")
    prefix = f"{path.as_posix()}::test_main_rejects_stale_archie_seal_"
    batches = runner["_heavy_test_batches"]((path,))

    stale_seal_batches = tuple(
        selectors
        for _batch_path, selectors in batches
        if any(selector.startswith(prefix) for selector in selectors)
    )

    assert stale_seal_batches == tuple(
        (f"{prefix}after_{change}_change",) for change in ("source", "axis", "dataset", "well")
    )


def test_gis_navigation_stale_context_cases_use_separate_native_processes() -> None:
    runner = runpy.run_path("scripts/run_tests.py")
    path = Path("tests/test_gis_profile_tablet_navigation.py")
    relative_path = path.as_posix()
    prefixes = (
        f"{relative_path}::test_main_rejects_stale_or_foreign_handoff",
        f"{relative_path}::test_panel_discards_stale_context",
    )

    assert runner["_test_file_shards"](1, (path,)) == ()
    batches = runner["_heavy_test_batches"]((path,))
    stale_context_batches = tuple(
        (batch_path, selectors)
        for batch_path, selectors in batches
        if any(selector.startswith(prefixes) for selector in selectors)
    )

    assert stale_context_batches == tuple(
        (relative_path, (f"{relative_path}::{name}",))
        for name in (
            "test_main_rejects_stale_or_foreign_handoff_after_curve_change",
            "test_main_rejects_stale_or_foreign_handoff_after_axis_change",
            "test_main_rejects_stale_or_foreign_handoff_with_invalid_row",
            "test_main_rejects_stale_or_foreign_handoff_after_dataset_change",
            "test_main_rejects_stale_or_foreign_handoff_after_well_change",
            "test_panel_discards_stale_context_after_source_change",
            "test_panel_discards_stale_context_after_axis_change",
            "test_panel_discards_stale_context",
            "test_panel_discards_stale_context_after_rebuild",
        )
    )


def test_las3_modal_reopen_cases_use_separate_native_processes() -> None:
    runner = runpy.run_path("scripts/run_tests.py")
    path = Path("tests/test_las3_modal_reopen_acceptance.py")
    relative_path = path.as_posix()

    assert runner["_test_file_shards"](1, (path,)) == ()
    assert runner["_heavy_test_batches"]((path,)) == tuple(
        (
            relative_path,
            (f"{relative_path}::test_las3_modal_reopen_{project_format}_{language.value}",),
        )
        for project_format in ("geolog_json", "geologpkg")
        for language in AppLanguage
    )


def test_windows_default_shards_limit_qt_state_accumulation() -> None:
    runner = runpy.run_path("scripts/run_tests.py")
    assert runner["_DEFAULT_WINDOWS_SHARDS"] >= 16


def test_docx_footer_cases_do_not_share_process_with_qt_gui_shards() -> None:
    runner = runpy.run_path("scripts/run_tests.py")
    path = Path("tests/test_report_document_control_docx_footer.py")
    nodes = runner["_top_level_test_nodes"](path)
    assert nodes
    assert runner["_test_file_shards"](16, (path,)) == ()
    batches = runner["_heavy_test_batches"]((path,))
    assert len(batches) == len(nodes)
    assert all(selected == path.as_posix() and len(cases) == 1 for selected, cases in batches)
    assert tuple(case for _selected, cases in batches for case in cases) == nodes


def test_grid_renderer_native_isolation_retains_every_test_node() -> None:
    """All grid-geometry and PlotWidget checks remain mandatory after native crash."""
    runner = runpy.run_path("scripts/run_tests.py")
    path = Path("tests/test_grid_renderer.py")
    nodes = runner["_top_level_test_nodes"](path)
    assert nodes
    assert len(nodes) >= 10
    assert (
        "tests/test_grid_renderer.py::"
        "test_depth_overlay_aligns_horizontal_lines_to_five_metre_values"
    ) in nodes
    assert runner["_requires_native_batch"](path, nodes) is True
    assert path.as_posix() in runner["_FORCED_NATIVE_BATCH_FILES"]
    assert path.as_posix() in runner["_SINGLE_TEST_PROCESS_FILES"]
    assert runner["_test_file_shards"](16, (path,)) == ()

    batches = runner["_heavy_test_batches"]((path,))
    assert len(batches) == len(nodes)
    assert all(batch_path == path.as_posix() and len(selectors) == 1
               for batch_path, selectors in batches)
    assert tuple(selector for _batch_path, selectors in batches
                 for selector in selectors) == nodes


def test_wits0_capture_dialog_native_batches_preserve_every_assertion() -> None:
    """CI may isolate a native Qt heap but must not skip capture scenarios."""
    runner = runpy.run_path("scripts/run_tests.py")
    path = Path("tests/test_wits0_capture_dialog.py")
    nodes = runner["_top_level_test_nodes"](path)
    assert len(nodes) >= 12
    assert (
        "tests/test_wits0_capture_dialog.py::"
        "test_wits0_capture_reports_synchronous_startup_failures"
    ) in nodes
    assert (
        "tests/test_wits0_capture_dialog.py::"
        "test_wits0_capture_dialog_constructs_offscreen"
    ) in nodes
    assert path.as_posix() in runner["_FORCED_NATIVE_BATCH_FILES"]
    assert path.as_posix() in runner["_SINGLE_TEST_PROCESS_FILES"]
    assert runner["_test_file_shards"](16, (path,)) == ()
    batches = runner["_heavy_test_batches"]((path,))
    assert len(batches) == len(nodes)
    assert all(name == path.as_posix() and len(selectors) == 1
               for name, selectors in batches)
    assert tuple(selector for _, selectors in batches for selector in selectors) == nodes


def test_well_numerical_save_scenarios_have_independent_native_lifetimes() -> None:
    """Five mandatory save-gate outcomes each construct MainWindow in a fresh process.

    Main after PR #723 / run 40089829503 aborted with 0xC0000005 in
    pyqtgraph ViewBoxMenu while the final parametrized case shared one
    QApplication with four earlier cases. This isolates Qt lifetimes only;
    it does not classify the unknown native root cause as fixed (#544).
    """
    runner = runpy.run_path("scripts/run_tests.py")
    path = Path("tests/test_well_update_workflow.py")
    nodes = runner["_top_level_test_nodes"](path)
    expected = tuple(
        f"{path.as_posix()}::test_main_window_numerical_save_gate_{scenario}"
        for scenario in ("save", "no_selection", "disk_full", "external", "cancel")
    )
    assert len(expected) == len(set(expected)) == 5
    assert all(node in nodes for node in expected)
    assert path.as_posix() in runner["_SINGLE_TEST_PROCESS_FILES"]
    batches = runner["_heavy_test_batches"]((path,))
    assert all(len(selectors) == 1 for _batch_path, selectors in batches)
    assert tuple(
        selectors[0] for _path, selectors in batches if selectors[0] in expected
    ) == expected
