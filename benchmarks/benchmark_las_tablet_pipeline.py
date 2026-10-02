from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any

from PySide6.QtWidgets import QApplication

import geoworkbench.data.las_adapter as las_adapter_module
from geoworkbench.data.las_adapter import import_las_with_report
from geoworkbench.services.process_metrics import process_memory_snapshot
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


DEFAULT_ROWS = 27_500
DEFAULT_CURVES = 351
DEFAULT_RENDER_TRACKS = 16
DEFAULT_WIDTH = 1600
DEFAULT_HEIGHT = 900


def _curve_mnemonic(index: int) -> str:
    return f"C{index:04d}"


def _write_fixture(path: Path, *, rows: int, curves: int) -> None:
    """Write a deterministic M-1-shaped LAS without retaining the file in memory."""

    stop = max(0.0, (rows - 1) * 0.2)
    header = [
        "~Version Information",
        "VERS. 2.0 : CWLS LOG ASCII STANDARD - VERSION 2.0",
        "WRAP. NO",
        "~Well Information",
        "STRT.M 0.0 : Start depth",
        f"STOP.M {stop:.3f} : Stop depth",
        "STEP.M 0.2 : Step",
        "NULL. -999.25 : Null value",
        "WELL. PERF07 : Synthetic performance fixture",
        "~Curve Information",
        "DEPT.M : Measured depth",
    ]
    header.extend(
        f"{_curve_mnemonic(index)}.ppm : Synthetic curve {index}"
        for index in range(1, curves + 1)
    )
    header.append("~ASCII")

    # Values are deterministic and intentionally precomputed once. Fixture creation
    # is outside the timed region; the benchmark measures production LAS parsing,
    # Dataset materialization and tablet presentation, not random-data generation.
    curve_values = " ".join(
        f"{1.0 + (index % 97) * 0.125:.3f}"
        for index in range(1, curves + 1)
    )
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write("\n".join(header))
        stream.write("\n")
        for row in range(rows):
            stream.write(f"{row * 0.2:.3f} {curve_values}\n")


def _layout(render_tracks: int) -> TabletLayout:
    return TabletLayout(
        [
            TrackDefinition(
                f"perf-{index:02d}",
                f"Curve {index:02d}",
                TrackKind.CURVE,
                curve_mnemonics=[_curve_mnemonic(index)],
            )
            for index in range(1, render_tracks + 1)
        ]
    )


def _maximum_peak_rss(*values: int | None) -> int | None:
    available = [value for value in values if value is not None]
    return max(available) if available else None


def _import_with_performance_event(source: Path):
    """Run the production importer and retain its existing observability payload."""

    captured: list[dict[str, object]] = []
    original_log_event = las_adapter_module.log_event

    def capture(event: str, **context: object) -> None:
        if event == "las.import.performance":
            captured.append(dict(context))
        original_log_event(event, **context)

    las_adapter_module.log_event = capture
    try:
        result = import_las_with_report(source)
    finally:
        las_adapter_module.log_event = original_log_event

    if len(captured) != 1:
        raise AssertionError(
            "production LAS import must emit exactly one performance event"
        )
    return result, captured[0]


def run_benchmark_worker(
    rows: int,
    *,
    curves: int = DEFAULT_CURVES,
    render_tracks: int = DEFAULT_RENDER_TRACKS,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> dict[str, Any]:
    if rows < 2:
        raise ValueError("rows must be at least 2")
    if curves < 1:
        raise ValueError("curves must be positive")
    if render_tracks < 1 or render_tracks > curves:
        raise ValueError("render_tracks must be within the available curve count")
    if width < 320 or height < 240:
        raise ValueError("benchmark viewport is too small")

    with TemporaryDirectory(prefix="geolog-perf07-") as temporary:
        source = Path(temporary) / "perf07_m1_shape.las"
        _write_fixture(source, rows=rows, curves=curves)
        source_size = source.stat().st_size

        memory_start = process_memory_snapshot()
        import_started = perf_counter()
        imported, import_performance = _import_with_performance_event(source)
        import_ms = (perf_counter() - import_started) * 1_000.0
        memory_after_import = process_memory_snapshot()

        application = QApplication.instance()
        owns_application = application is None
        if application is None:
            application = QApplication([])
        assert application is not None

        view = TabletView()
        view.resize(width, height)
        view.show()
        application.processEvents()

        before_render = view.dirty_render_stats()
        render_started = perf_counter()
        view.set_layout_and_dataset(
            _layout(render_tracks),
            imported.dataset,
            preserve_current_range=False,
        )
        application.processEvents()
        first_render_ms = (perf_counter() - render_started) * 1_000.0
        after_render = view.dirty_render_stats()
        cache_after_render = view.geometry_cache_stats()
        memory_after_render = process_memory_snapshot()

        scroll_started = perf_counter()
        scroll_changed = view.scroll_depth(1.0)
        application.processEvents()
        scroll_ms = (perf_counter() - scroll_started) * 1_000.0

        visible = view.visible_depth_range
        anchor = sum(visible) / 2.0 if visible is not None else None
        zoom_started = perf_counter()
        zoom_changed = view.zoom_depth(0.5, anchor=anchor)
        application.processEvents()
        zoom_ms = (perf_counter() - zoom_started) * 1_000.0

        after_navigation = view.dirty_render_stats()
        cache_after_navigation = view.geometry_cache_stats()
        memory_after_navigation = process_memory_snapshot()

        result: dict[str, Any] = {
            "input_rows": rows,
            "input_curves": curves,
            "render_tracks": render_tracks,
            "source_size_bytes": source_size,
            "imported_rows": int(imported.dataset.depth.size),
            "imported_curves": len(imported.dataset.curves),
            "import_warning_count": imported.report.warning_count,
            "import_ms": import_ms,
            "import_source_ms": import_performance["source_ms"],
            "import_parse_ms": import_performance["parse_ms"],
            "import_dataset_ms": import_performance["dataset_ms"],
            "import_report_ms": import_performance["report_ms"],
            "import_logged_total_ms": import_performance["total_ms"],
            "import_rss_source_bytes": import_performance["rss_source_bytes"],
            "import_rss_parse_bytes": import_performance["rss_parse_bytes"],
            "import_rss_dataset_bytes": import_performance["rss_dataset_bytes"],
            "import_rss_report_bytes": import_performance["rss_report_bytes"],
            "first_render_ms": first_render_ms,
            "scroll_ms": scroll_ms,
            "zoom_ms": zoom_ms,
            "scroll_changed": bool(scroll_changed),
            "zoom_changed": bool(zoom_changed),
            "rendered_tracks": len(view._rendered),
            "first_render_full_updates_delta": (
                after_render.full_updates - before_render.full_updates
            ),
            "navigation_full_updates_delta": (
                after_navigation.full_updates - after_render.full_updates
            ),
            "partial_updates_after_render": after_render.partial_updates,
            "partial_updates_after_navigation": after_navigation.partial_updates,
            "geometry_cache_hits_after_render": cache_after_render.hits,
            "geometry_cache_misses_after_render": cache_after_render.misses,
            "geometry_cache_entries_after_render": cache_after_render.entries,
            "geometry_cache_hits_after_navigation": cache_after_navigation.hits,
            "geometry_cache_misses_after_navigation": cache_after_navigation.misses,
            "geometry_cache_entries_after_navigation": cache_after_navigation.entries,
            "rss_start_bytes": memory_start.rss_bytes,
            "rss_after_import_bytes": memory_after_import.rss_bytes,
            "rss_after_render_bytes": memory_after_render.rss_bytes,
            "rss_after_navigation_bytes": memory_after_navigation.rss_bytes,
            "peak_rss_bytes": _maximum_peak_rss(
                memory_start.peak_rss_bytes,
                memory_after_import.peak_rss_bytes,
                memory_after_render.peak_rss_bytes,
                memory_after_navigation.peak_rss_bytes,
            ),
        }

        view.close()
        application.processEvents()
        if owns_application:
            application.quit()

    evaluate_result(result)
    return result


def evaluate_result(result: dict[str, Any]) -> None:
    if result["imported_rows"] != result["input_rows"]:
        raise AssertionError("LAS import changed the row count")
    if result["imported_curves"] != result["input_curves"]:
        raise AssertionError("LAS import changed the curve count")
    if result["rendered_tracks"] != result["render_tracks"]:
        raise AssertionError("tablet did not materialize every requested track")
    if result["first_render_full_updates_delta"] != 1:
        raise AssertionError("first presentation must use exactly one full tablet rebuild")
    if not result["scroll_changed"] or not result["zoom_changed"]:
        raise AssertionError("scroll and zoom must both exercise a changed viewport")
    if result["navigation_full_updates_delta"] != 0:
        raise AssertionError("scroll/zoom must not trigger a full tablet rebuild")
    if result["geometry_cache_misses_after_render"] < result["render_tracks"]:
        raise AssertionError("first render did not exercise production curve geometry")
    if (
        result["geometry_cache_misses_after_navigation"]
        < result["geometry_cache_misses_after_render"]
    ):
        raise AssertionError("navigation geometry-cache counters moved backwards")
    for key in (
        "import_ms",
        "import_source_ms",
        "import_parse_ms",
        "import_dataset_ms",
        "import_report_ms",
        "import_logged_total_ms",
        "first_render_ms",
        "scroll_ms",
        "zoom_ms",
    ):
        if result[key] < 0:
            raise AssertionError(f"{key} must be non-negative")
    phase_total = (
        result["import_source_ms"]
        + result["import_parse_ms"]
        + result["import_dataset_ms"]
        + result["import_report_ms"]
    )
    if abs(phase_total - result["import_logged_total_ms"]) > 2.0:
        raise AssertionError("LAS import phase timings no longer cover logged total time")
    peak_rss = result["peak_rss_bytes"]
    if peak_rss is not None and peak_rss <= 0:
        raise AssertionError("peak RSS must be positive when the platform exposes it")


def run_isolated_benchmark(
    rows: int,
    *,
    curves: int = DEFAULT_CURVES,
    render_tracks: int = DEFAULT_RENDER_TRACKS,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--rows",
        str(rows),
        "--curves",
        str(curves),
        "--render-tracks",
        str(render_tracks),
        "--width",
        str(width),
        "--height",
        str(height),
    ]
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    if completed.returncode != 0:
        details = completed.stderr.strip() or completed.stdout.strip() or "unknown worker failure"
        raise RuntimeError(f"PERF-07 worker failed: {details}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"PERF-07 worker returned invalid JSON: {completed.stdout!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("PERF-07 worker returned non-object JSON")
    return payload


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PERF-07 LAS import and tablet presentation benchmark"
    )
    parser.add_argument("--rows", type=_positive_int, default=DEFAULT_ROWS)
    parser.add_argument("--curves", type=_positive_int, default=DEFAULT_CURVES)
    parser.add_argument(
        "--render-tracks", type=_positive_int, default=DEFAULT_RENDER_TRACKS
    )
    parser.add_argument("--width", type=_positive_int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=_positive_int, default=DEFAULT_HEIGHT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.render_tracks > args.curves:
        raise ValueError("render_tracks cannot exceed curves")
    if args.worker:
        result = run_benchmark_worker(
            args.rows,
            curves=args.curves,
            render_tracks=args.render_tracks,
            width=args.width,
            height=args.height,
        )
        print(json.dumps(result, sort_keys=True))
        return 0

    result = run_isolated_benchmark(
        args.rows,
        curves=args.curves,
        render_tracks=args.render_tracks,
        width=args.width,
        height=args.height,
    )
    payload = {
        "contract": {
            "fixture": "synthetic-m1-shape",
            "rows": args.rows,
            "curves": args.curves,
            "render_tracks": args.render_tracks,
            "viewport": [args.width, args.height],
            "timing_thresholds": None,
            "enforced": [
                "import row/curve preservation",
                "exactly one initial full rebuild",
                "no full rebuild during scroll/zoom",
                "production geometry cache exercised",
            ],
        },
        "result": result,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "rows={input_rows:,} curves={input_curves} tracks={render_tracks} "
            "import={import_ms:.3f}ms first_render={first_render_ms:.3f}ms "
            "scroll={scroll_ms:.3f}ms zoom={zoom_ms:.3f}ms peak_rss={peak_rss_bytes}".format(
                **result
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
