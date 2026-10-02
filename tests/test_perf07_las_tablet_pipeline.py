from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from benchmarks.benchmark_las_tablet_pipeline import (
    DEFAULT_CURVES,
    DEFAULT_RENDER_TRACKS,
    DEFAULT_ROWS,
    evaluate_result,
    run_benchmark_worker,
)

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.services.process_metrics import ProcessMemorySnapshot
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


def _valid_result() -> dict[str, object]:
    return {
        "input_rows": 1_000,
        "input_curves": 8,
        "render_tracks": 4,
        "imported_rows": 1_000,
        "imported_curves": 8,
        "rendered_tracks": 4,
        "first_render_full_updates_delta": 1,
        "scroll_changed": True,
        "zoom_changed": True,
        "navigation_full_updates_delta": 0,
        "geometry_cache_misses_after_render": 4,
        "geometry_cache_misses_after_navigation": 12,
        "import_ms": 10.0,
        "import_source_ms": 1.0,
        "import_parse_ms": 6.0,
        "import_parse_stream_setup_ms": 0.1,
        "import_parse_lasio_ms": 5.8,
        "import_parse_index_ms": 0.1,
        "import_dataset_ms": 2.0,
        "import_dataset_setup_ms": 0.2,
        "import_dataset_curve_values_ms": 0.4,
        "import_dataset_curve_canonical_ms": 0.5,
        "import_dataset_curve_semantic_ms": 0.5,
        "import_dataset_curve_store_ms": 0.3,
        "import_dataset_headers_ms": 0.1,
        "import_report_ms": 1.0,
        "import_logged_total_ms": 10.0,
        "first_render_ms": 2.0,
        "scroll_ms": 0.5,
        "zoom_ms": 0.5,
        "peak_rss_bytes": 1024,
    }


def test_perf07_contract_matches_current_m1_shape_and_release_gate() -> None:
    assert DEFAULT_ROWS == 27_500
    assert DEFAULT_CURVES == 351
    assert DEFAULT_RENDER_TRACKS == 16

    workflow = Path(".github/workflows/release-gate.yml").read_text(encoding="utf-8")
    assert "benchmark_las_tablet_pipeline.py --json" in workflow


def test_perf07_guardrail_rejects_full_rebuild_during_navigation() -> None:
    result = _valid_result()
    result["navigation_full_updates_delta"] = 1

    with pytest.raises(AssertionError, match="scroll/zoom"):
        evaluate_result(result)


def test_perf07_guardrail_rejects_negative_parse_subphase() -> None:
    result = _valid_result()
    result["import_parse_lasio_ms"] = -0.1

    with pytest.raises(AssertionError, match="import_parse_lasio_ms"):
        evaluate_result(result)


def test_perf07_worker_exercises_import_render_scroll_and_zoom(qapp) -> None:
    result = run_benchmark_worker(
        1_000,
        curves=8,
        render_tracks=4,
        width=900,
        height=650,
    )

    assert result["imported_rows"] == 1_000
    assert result["imported_curves"] == 8
    assert result["rendered_tracks"] == 4
    assert result["first_render_full_updates_delta"] == 1
    assert result["navigation_full_updates_delta"] == 0
    assert result["scroll_changed"] is True
    assert result["zoom_changed"] is True
    assert result["geometry_cache_misses_after_render"] >= 4
    assert result["import_source_ms"] >= 0
    assert result["import_parse_ms"] >= 0
    assert result["import_parse_stream_setup_ms"] >= 0
    assert result["import_parse_lasio_ms"] >= 0
    assert result["import_parse_index_ms"] >= 0
    assert result["import_dataset_ms"] >= 0
    assert result["import_dataset_setup_ms"] >= 0
    assert result["import_dataset_curve_values_ms"] >= 0
    assert result["import_dataset_curve_canonical_ms"] >= 0
    assert result["import_dataset_curve_semantic_ms"] >= 0
    assert result["import_dataset_curve_store_ms"] >= 0
    assert result["import_dataset_headers_ms"] >= 0
    assert result["import_report_ms"] >= 0
    assert result["import_logged_total_ms"] == pytest.approx(
        result["import_source_ms"]
        + result["import_parse_ms"]
        + result["import_dataset_ms"]
        + result["import_report_ms"],
        abs=2.0,
    )


def test_full_tablet_rebuild_log_includes_duration_and_rss(qapp, monkeypatch) -> None:
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "geoworkbench.tablet.tablet_view.process_memory_snapshot",
        lambda: ProcessMemorySnapshot(100, 200),
    )
    monkeypatch.setattr(
        "geoworkbench.tablet.tablet_view.log_event",
        lambda event, **context: events.append((event, context)),
    )

    depth = np.linspace(0.0, 100.0, 501, dtype=np.float64)
    dataset = Dataset(
        "perf07-observability",
        "PERF-07 observability",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    curve = CurveData(
        CurveMetadata(
            "curve-c1",
            "C1",
            "C1",
            "ppm",
            "Methane",
            dataset.dataset_id,
        ),
        np.linspace(1.0, 10.0, depth.size, dtype=np.float64),
    )
    dataset.curves[curve.metadata.curve_id] = curve

    view = TabletView()
    view.set_layout_and_dataset(
        TabletLayout(
            [
                TrackDefinition(
                    "gas",
                    "Gas",
                    TrackKind.CURVE,
                    curve_mnemonics=["C1"],
                )
            ]
        ),
        dataset,
        preserve_current_range=False,
    )
    qapp.processEvents()

    finished = [
        context
        for event, context in events
        if event == "tablet.render.full.finished"
    ]
    assert len(finished) == 1
    context = finished[0]
    assert context["rendered_tracks"] == 1
    assert context["duration_ms"] >= 0
    assert context["rss_start_bytes"] == 100
    assert context["rss_end_bytes"] == 100
    assert context["peak_rss_bytes"] == 200
    view.close()
