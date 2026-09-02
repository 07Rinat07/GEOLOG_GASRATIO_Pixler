from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import fitz
import numpy as np

from geoworkbench.calculations.gas_ratio import calculate_conditioned_ratios
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.printing.document_export import export_document_pdf
from geoworkbench.printing.document_renderer import PrintDocumentContext, build_document_plan
from geoworkbench.printing.page_settings import (
    PrintOrientation,
    PrintPageFormat,
    PrintPageSettings,
)
from geoworkbench.printing.pagination import PrintPaginationSettings, PrintRangeMode
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
from geoworkbench.printing.print_layout import PrintScaleMode
from geoworkbench.tablet.curve_scaling import automatic_curve_range
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind, XScale
from geoworkbench.tablet.tablet_view import TabletView


_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "gas_ratio"
    / "gas_07_sparse_c1_c5_v1.json"
)


def _load_case() -> dict[str, Any]:
    with _FIXTURE.open("r", encoding="utf-8") as handle:
        case = json.load(handle)
    assert case["case_id"] == "GAS-07"
    assert case["schema_version"] == 1
    return case


def _source_arrays(case: dict[str, Any]) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    axis = case["axis"]
    count = int(axis["count"])
    depth = float(axis["start"]) + np.arange(count, dtype=np.float64) * float(
        axis["step"]
    )
    components: dict[str, np.ndarray] = {}
    for mnemonic, anchors in case["components"].items():
        values = np.full(count, np.nan, dtype=np.float64)
        for sample_index, value in anchors:
            values[int(sample_index)] = float(value)
        components[str(mnemonic)] = values
    return depth, components


def _sample_index(depth: np.ndarray, probe_depth: float) -> int:
    matches = np.flatnonzero(
        np.isclose(depth, float(probe_depth), rtol=0.0, atol=1e-9)
    )
    assert matches.size == 1, f"probe depth {probe_depth} is not unique"
    return int(matches[0])


def _build_tablet(
    depth: np.ndarray,
    conditioned_components: dict[str, np.ndarray],
    derived_curves: dict[str, Any],
) -> TabletView:
    dataset = Dataset(
        "gas-07-golden",
        "GAS-07 golden acceptance",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    for mnemonic, values in conditioned_components.items():
        dataset.upsert_curve(
            mnemonic,
            values,
            unit="%abs",
            description=f"GAS-07 conditioned {mnemonic}",
        )
    for mnemonic in ("TG_CALC", "PIXLER_C1_C2", "PIXLER_C1_C3", "IC4_NC4"):
        curve = derived_curves[mnemonic]
        dataset.upsert_curve(
            mnemonic,
            curve.values,
            unit=curve.unit,
            description=curve.description,
        )

    view = TabletView()
    view.resize(1000, 760)
    view.set_layout_and_dataset(
        TabletLayout(
            tracks=[
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=80),
                TrackDefinition(
                    "components",
                    "C1-C5",
                    TrackKind.GAS,
                    width=230,
                    curve_mnemonics=[
                        "C1",
                        "C2",
                        "C3",
                        "IC4",
                        "NC4",
                        "IC5",
                        "NC5",
                    ],
                ),
                TrackDefinition(
                    "total",
                    "Total gas",
                    TrackKind.GAS,
                    width=130,
                    curve_mnemonics=["TG_CALC"],
                ),
                TrackDefinition(
                    "ratios",
                    "Pixler ratios",
                    TrackKind.GAS,
                    width=180,
                    curve_mnemonics=[
                        "PIXLER_C1_C2",
                        "PIXLER_C1_C3",
                        "IC4_NC4",
                    ],
                ),
            ],
            visible_depth_top=float(depth[0]),
            visible_depth_bottom=float(depth[-1]),
        ),
        dataset,
    )
    return view


def _assert_rendered_segmentation(
    item: Any,
    *,
    connected_depth: float,
    broken_depth: float,
) -> None:
    x_values, y_values = item.getData()
    assert x_values is not None and y_values is not None
    rendered_depth = np.asarray(y_values, dtype=np.float64)
    rendered_values = np.asarray(x_values, dtype=np.float64)
    connected_index = _sample_index(rendered_depth, connected_depth)
    broken_index = _sample_index(rendered_depth, broken_depth)

    assert np.isfinite(rendered_values[connected_index])
    assert np.isnan(rendered_values[broken_index])

    connect = item.curve.opts["connect"]
    if isinstance(connect, np.ndarray):
        assert connect.dtype == np.bool_
        assert connect.shape == rendered_depth.shape
        assert bool(connect[connected_index])
        assert not bool(connect[broken_index])
    else:
        assert connect in ("auto", "finite")

    assert item.opts.get("symbol") is None


def test_gas_07_golden_dataset_through_production_pipeline(
    qapp,
    tmp_path: Path,
) -> None:
    case = _load_case()
    depth, source_components = _source_arrays(case)
    expected = case["expected"]

    result = calculate_conditioned_ratios(depth, source_components)

    short_probe = expected["short_gap_probe"]
    short_index = _sample_index(depth, float(short_probe["depth"]))
    for mnemonic, expected_value in short_probe["components"].items():
        actual = result.conditioned_components.components[mnemonic][short_index]
        assert result.conditioned_components.interpolated_masks[mnemonic][short_index]
        assert np.isclose(actual, float(expected_value), rtol=1e-12, atol=1e-12)

    for mnemonic, expected_value in short_probe["derived"].items():
        actual = result.curves[mnemonic].values[short_index]
        assert np.isclose(actual, float(expected_value), rtol=1e-12, atol=1e-12)

    outage_probe = expected["long_outage_probe"]
    outage_index = _sample_index(depth, float(outage_probe["depth"]))
    for mnemonic in outage_probe["missing"]:
        if mnemonic in result.conditioned_components.components:
            actual = result.conditioned_components.components[mnemonic][outage_index]
        else:
            actual = result.curves[mnemonic].values[outage_index]
        assert np.isnan(actual), f"{mnemonic} must remain missing across the long outage"

    scale_expected = expected["scale_bounds"]
    c1_scale = automatic_curve_range(
        result.conditioned_components.components["C1"],
        XScale.LINEAR,
    )
    tg_scale = automatic_curve_range(result.curves["TG_CALC"].values, XScale.LINEAR)
    np.testing.assert_allclose(
        c1_scale,
        np.asarray(scale_expected["C1_LINEAR"], dtype=np.float64),
        rtol=0.0,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        tg_scale,
        np.asarray(scale_expected["TG_CALC_LINEAR"], dtype=np.float64),
        rtol=0.0,
        atol=1e-12,
    )

    tablet = _build_tablet(
        depth,
        result.conditioned_components.components,
        result.curves,
    )
    tablet.show()
    qapp.processEvents()
    target = tmp_path / "gas-07-golden.pdf"

    try:
        segment_expected = expected["segmentation"]
        _assert_rendered_segmentation(
            tablet._rendered["components"].curve_items["C1"],
            connected_depth=float(segment_expected["connected_probe_depth"]),
            broken_depth=float(segment_expected["broken_probe_depth"]),
        )

        pagination = expected["pagination"]
        job = PrintJobSettings(
            output_format=PrintOutputFormat.PDF,
            target=target,
            dpi=150,
            page=PrintPageSettings(
                page_format=PrintPageFormat.A4,
                orientation=PrintOrientation.LANDSCAPE,
                scale_mode=PrintScaleMode.FIT,
            ),
            pagination=PrintPaginationSettings(
                range_mode=PrintRangeMode.FULL,
                units_per_page=float(pagination["units_per_page"]),
                overlap=float(pagination["overlap"]),
            ),
            repeat_column_header_at_bottom=False,
            strict_unicode=False,
        )
        context = PrintDocumentContext("GAS-07 golden acceptance")
        plan = build_document_plan(tablet, job, context=context)
        actual_pages = [
            [float(page.start), float(page.end)]
            for page in plan.pages
            if page.has_vertical_range
            and page.start is not None
            and page.end is not None
        ]
        np.testing.assert_allclose(
            actual_pages,
            np.asarray(pagination["pages"], dtype=np.float64),
            rtol=0.0,
            atol=1e-9,
        )
        assert plan.page_count == int(pagination["pdf_page_count"])

        export_result = export_document_pdf(
            tablet,
            target,
            job,
            context=context,
            overwrite=True,
        )
    finally:
        tablet.close()
        qapp.processEvents()

    assert export_result.page_count == int(expected["pagination"]["pdf_page_count"])
    assert target.exists()
    assert target.stat().st_size > 0
    with fitz.open(target) as document:
        assert document.page_count == int(expected["pagination"]["pdf_page_count"])
        for page in document:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5), alpha=False)
            assert pixmap.samples
            assert min(pixmap.samples) < 250
