"""Temporary Windows Qt/Masterlog native-heap replay (not a release gate)."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

from scripts.run_tests import _configure_environment, _run_child, _test_file_shards


# Recovered from the six-file seed in Windows replay 42526104945. Explicit file
# names prevent unrelated test-suite changes from silently changing this prefix.
SEED_FILES = (
    "tests/test_gas_curve_rendering_continuity.py",
    "tests/test_gas_interval_gis_review_ui.py",
    "tests/test_gas_interval_gis_source_review_ui.py",
    "tests/test_gas_mixture_line_patterns.py",
    "tests/test_gas_mixture_output_language.py",
    "tests/test_gas_update_coverage.py",
)
TARGET_FILE = "tests/test_masterlog_columns_dialog.py"
RESAMPLE_UNDO_FILE = "tests/test_main_window.py"
RESAMPLE_UNDO_NODE = (
    "tests/test_main_window.py::test_window_creates_and_undoes_resampled_copy"
)
NORMALIZED_GAS_FILE = "tests/test_main_window_normalized_gas_tablet.py"
NORMALIZED_GAS_NODE = (
    "tests/test_main_window_normalized_gas_tablet.py"
    "::test_show_normalized_gas_button_opens_tablet_and_adds_track"
)

# Exact 9/16 regular shard captured from main 726a22f / run 42462681087,
# attempt 7. Run the same selectors together to reproduce the native heap fault.
MAIN_FAILED_SHARD_FILES = (
    "tests/test_las3_scalar_log_preview.py",
    "tests/test_las3_section_inventory.py",
    "tests/test_las3_tablet_render_acceptance.py",
    "tests/test_las_curve_browser.py",
    "tests/test_las_editor_dialog.py",
    "tests/test_las_export_dialog.py",
    "tests/test_las_export_plan.py",
    "tests/test_las_geology_dialect.py",
    "tests/test_las_growth_analysis_task.py",
    "tests/test_las_import_policy.py",
    "tests/test_las_numeric_line_iteration.py",
    "tests/test_las_parameter_resolver.py",
    "tests/test_las_range_editor.py",
    "tests/test_las_table_editor.py",
    "tests/test_late_analysis_adapter.py",
    "tests/test_late_analysis_coordinator.py",
    "tests/test_late_analysis_review_dialog.py",
    "tests/test_layout_transaction.py",
    "tests/test_lba_color_labels.py",
    "tests/test_lba_label_orientation.py",
    "tests/test_lba_operator_screening.py",
    "tests/test_lba_standard.py",
    "tests/test_lba_visuals.py",
    "tests/test_legacy_geosight_forms.py",
    "tests/test_lithology_controller.py",
    "tests/test_lithology_dialog.py",
    "tests/test_lithology_interval_dialog.py",
    "tests/test_lithology_labels.py",
    "tests/test_lithology_legend.py",
    "tests/test_lithology_legend_dialog.py",
    "tests/test_lithology_pattern_catalog.py",
    "tests/test_lithology_patterns.py",
    "tests/test_lithology_review_comparison.py",
    "tests/test_lithology_review_export.py",
    "tests/test_lithology_review_history.py",
    "tests/test_lithology_review_reader.py",
    "tests/test_lithology_revision_proposal.py",
    "tests/test_lithology_source_mapping.py",
    "tests/test_lithology_translation_tracking.py",
    "tests/test_lithology_translation_tracking_dialog.py",
    "tests/test_lithotype_catalog.py",
    "tests/test_lithotype_catalog_controller.py",
    "tests/test_lithotype_catalog_dialog.py",
    "tests/test_logo_catalog.py",
    "tests/test_lossless_las.py",
    "tests/test_main_shell_presentation.py",
    "tests/test_manual_backup_dialog.py",
    "tests/test_manual_backup_restore_preview_dialog.py",
    "tests/test_masterlog_assets_dialog.py",
    "tests/test_masterlog_bundle_exporter.py",
    "tests/test_masterlog_bundle_preflight.py",
    "tests/test_masterlog_callout_unicode.py",
    "tests/test_masterlog_columns_dialog.py",
    "tests/test_masterlog_control_layout.py",
)

_NATIVE_EXCEPTION = re.compile(
    r"ExceptionCode:\s*(?:0x)?c000(?:0005|0374|0409)\b"
    r"|Windows fatal exception:\s*code\s*0xc000(?:0005|0374|0409)\b"
    r"|second chance !!!"
    r"|Fatal Python error:",
    re.IGNORECASE,
)
_CDB_ARMED_MARKER = re.compile(r"(?m)^[ \t]*GEOLOG_CDB_ARMED[ \t]*$")
_CDB_EXCEPTION_MARKER = re.compile(
    r"(?m)^[ \t]*GEOLOG_CDB_NATIVE_EXCEPTION[ \t]*$"
)
_PYTEST_COLLECTED = re.compile(
    r"(?m)^(?:collecting \.\.\. )?collected ([1-9]\d*) items?[ \t]*$",
    re.IGNORECASE,
)
_PYTEST_COMPLETE = re.compile(
    r"(?m)^=+\s*([1-9]\d*) passed\b[^\r\n]*\bin\s+\d+(?:\.\d+)?s\s*=+[ \t]*$",
    re.IGNORECASE,
)
# Any incomplete execution invalidates a diagnostic success, even if pytest
# returns zero (for example, an unexpected skip or deselection).
_PYTEST_INCOMPLETE = re.compile(
    r"\b[1-9]\d*\s+(?:skipped|xfailed|xpassed|deselected|reruns?)\b",
    re.IGNORECASE,
)
_PYTEST_FAILURES = re.compile(
    r"=+\s*[^\r\n]*\b[1-9]\d*\s+(?:failed|errors?)\b",
    re.IGNORECASE,
)


def debugger_replay_passed(returncode: int, output: str) -> bool:
    """Require exactly one complete pytest collection and matching pass count.

    CDB can quit with status zero after a partial run. The Python child reports
    either 'collecting ... collected N items' or 'collected N items' when CDB
    interleaves module-load messages. Neither a summary alone nor an unrelated
    native exception marker establishes complete test execution.
    """
    collected = _PYTEST_COLLECTED.findall(output)
    completed = _PYTEST_COMPLETE.findall(output)
    return (
        returncode == 0
        and _CDB_ARMED_MARKER.search(output) is not None
        and _CDB_EXCEPTION_MARKER.search(output) is None
        and _NATIVE_EXCEPTION.search(output) is None
        and _PYTEST_FAILURES.search(output) is None
        and _PYTEST_INCOMPLETE.search(output) is None
        and len(collected) == 1
        and len(completed) == 1
        and collected[0] == completed[0]
    )


def _cdb_startup_commands(dump_path: Path) -> str:
    """Arm native-exception capture before resuming the Python process.

    -cf runs at the debugger's initial breakpoint. The -c startup option must
    not be used to take a dump: that would run before the target faults.
    """
    if any(char in str(dump_path) for char in (' ', '"', ';')):
        raise ValueError("CDB dump path must not contain spaces or commands")
    capture = (
        ".echo GEOLOG_CDB_NATIVE_EXCEPTION; .exr -1; r; kv; lm; "
        f".dump /m {dump_path}; q"
    )
    return "\n".join(
        (
            f'sxe -c "{capture}" 0xc0000374',
            f'sxd -c2 "{capture}" av',
            f'sxd -c2 "{capture}" 0xc0000409',
            # The real python.exe starts as a child of venvlauncher.exe.
            # Its initial (ibp) break is a debugger event, not a crash.
            "sxn ibp",
            ".echo GEOLOG_CDB_ARMED",
            "g",
            "",
        )
    )


def _run_debugged_target(selectors: tuple[str, ...], environment: dict[str, str]) -> int:
    debugger = (
        Path(os.environ["ProgramFiles(x86)"]) / "Windows Kits/10/Debuggers/x64/cdb.exe"
    )
    dump_path = Path(os.environ["RUNNER_TEMP"]) / "geolog-replay-dumps/qt-native.dmp"
    if not debugger.is_file():
        raise RuntimeError("CDB debugger not installed on Windows runner")
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    startup_file = dump_path.parent / "cdb-startup.txt"
    startup_file.write_text(_cdb_startup_commands(dump_path), encoding="ascii")

    # Debug child Python behind Windows venvlauncher.exe. Do not use -g:
    # it would skip the initial breakpoint needed to install filters.
    # Disable CDB debug heap (-hd) so heap corruption is tested on the
    # same standard Windows heap as the mandatory Quality gate.
    # The installed exception commands print native registers, stack, modules
    # and write a bounded dump only after an actual fatal exception.
    command = [
        str(debugger), "-o", "-hd", "-G", "-cf", str(startup_file),
        sys.executable, "scripts/run_tests.py", "--geolog-single-shard",
        "-s", "-p", "no:cacheprovider", *selectors,
    ]
    completed = subprocess.run(
        command,
        env=environment,
        check=False,
        timeout=1200,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print(completed.stdout, end="", flush=True)
    if not debugger_replay_passed(completed.returncode, completed.stdout):
        print(
            "Diagnostic replay FAILED or INCOMPLETE: "
            f"CDB status={completed.returncode}; "
            f"armed={_CDB_ARMED_MARKER.search(completed.stdout) is not None}; "
            f"exception_marker={_CDB_EXCEPTION_MARKER.search(completed.stdout) is not None}. "
            "CDB exit alone is not proof that pytest finished successfully.",
            file=sys.stderr,
            flush=True,
        )
        return 1
    return 0


def _run_plain_target(selectors: tuple[str, ...], environment: dict[str, str]) -> int:
    """Control: run the same native Qt shard without debugger instrumentation.

    A nonzero process status, including 0xC0000374, is still a failure.
    Windows Error Reporting is configured by the workflow for dump collection.
    """
    return _run_child(("-s", "-p", "no:cacheprovider"), selectors, environment)


def select_target_group(shards: tuple[tuple[str, ...], ...]) -> tuple[str, ...]:
    """Keep Masterlog replay usable after the runner moves it to native batches.

    Before the Qt containment fix the target lived in a shared regular shard.
    After that fix the file is explicitly excluded from regular shards, but the
    diagnostic must still execute it as a standalone target rather than abort.
    """
    return next(
        (selectors for selectors in shards if TARGET_FILE in selectors),
        (TARGET_FILE,),
    )


def main() -> int:
    shards = _test_file_shards(16)
    target_shard = select_target_group(shards)
    mode = os.environ.get("GEOLOG_REPLAY_MODE", "plain-shard")
    if mode not in {"isolated", "sequence", "both", "failing-shard", "plain-shard", "resample-undo", "normalized-gas"}:
        raise ValueError(
            "Select plain-shard, failing-shard, resample-undo, normalized-gas, isolated, sequence, or both"
        )
    try:
        repetitions = int(os.environ.get("GEOLOG_REPLAY_REPETITIONS", "1"))
    except ValueError as exc:
        raise ValueError("Invalid replay repetitions") from exc
    if not 1 <= repetitions <= 4:
        raise ValueError("Replay repetitions must be between 1 and 4")
    selectors = (
        (RESAMPLE_UNDO_FILE,)
        if mode == "resample-undo"
        else (NORMALIZED_GAS_FILE,)
        if mode == "normalized-gas"
        else MAIN_FAILED_SHARD_FILES
        if mode in {"failing-shard", "plain-shard"}
        else (*SEED_FILES, *target_shard)
    )
    if any(not Path(name).is_file() for name in selectors):
        raise RuntimeError("Expected replay selectors are missing")

    _configure_environment()
    environment = os.environ.copy()
    for repetition in range(1, repetitions + 1):
        if mode in {"resample-undo", "normalized-gas"}:
            # Both native crash sites are tested once without a debugger and
            # once with CDB. One failure cannot be hidden by the other control.
            node = (
                (RESAMPLE_UNDO_NODE,)
                if mode == "resample-undo"
                else (NORMALIZED_GAS_NODE,)
            )
            print(
                f"Diagnostic {repetition}/{repetitions}: {mode} without CDB",
                flush=True,
            )
            plain_result = _run_plain_target(node, environment)
            print(
                f"Diagnostic {repetition}/{repetitions}: {mode} under CDB",
                flush=True,
            )
            cdb_result = _run_debugged_target(node, environment)
            if plain_result or cdb_result:
                return 1
        if mode == "plain-shard":
            print(
                f"Diagnostic {repetition}/{repetitions}: exact main shard, no debugger",
                flush=True,
            )
            if _run_plain_target(MAIN_FAILED_SHARD_FILES, environment):
                return 1
        if mode == "failing-shard":
            print(f"Diagnostic {repetition}/{repetitions}: exact failed main shard", flush=True)
            if _run_debugged_target(MAIN_FAILED_SHARD_FILES, environment):
                return 1
        if mode in {"isolated", "both"}:
            # A genuine isolated control must not import the six-file seed.
            # Keep it distinct from the seeded CDB sequence used for diagnosis.
            print(
                f"Diagnostic {repetition}/{repetitions}: isolated Masterlog target",
                flush=True,
            )
            result = _run_child(
                ("-p", "no:cacheprovider"), (TARGET_FILE,), environment
            )
            if result:
                return 1
        if mode in {"sequence", "both"}:
            print(f"Diagnostic {repetition}/{repetitions}: seed shard", flush=True)
            result = _run_child(
                ("-p", "no:cacheprovider"), SEED_FILES, environment
            )
            if result:
                return 1
            print(f"Diagnostic {repetition}/{repetitions}: CDB target", flush=True)
            if _run_debugged_target(target_shard, environment):
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
