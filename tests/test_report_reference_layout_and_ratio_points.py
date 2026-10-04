from __future__ import annotations

import inspect

import numpy as np

from geoworkbench.printing.hydrocarbon_interpretation_pdf_renderer import (
    render_hydrocarbon_interpretation_report,
)
from geoworkbench.services.gas_curve_presentation import (
    GAS_PRINT_POINT_RADIUS_PT,
    gas_scatter_point_budget,
    select_gas_scatter_samples,
)


def test_reference_material_forces_methodology_onto_page_after_geology_legend() -> None:
    source = inspect.getsource(render_hydrocarbon_interpretation_report)
    legend_loop = source.index("for legend_page in legend_pages:")
    methodology = source.index("if key_html:", legend_loop)
    methodology_render = source.index("render_report_html(", methodology)

    assert "paginate_geology_legend(" in source[legend_loop - 700 : legend_loop]
    assert "canvas.new_page()" in source[methodology:methodology_render]
    assert "chart_legend_mode = (" in source[methodology_render:]
    assert "ReportLegendMode.COMPACT" in source[methodology_render:]


def test_dense_ratio_budget_keeps_point_trace_readable_without_sparse_sampling() -> None:
    assert gas_scatter_point_budget(460.0) >= 390
    assert gas_scatter_point_budget(1200.0) >= 1000
    assert GAS_PRINT_POINT_RADIUS_PT <= 0.6


def test_dense_ratio_sampler_keeps_one_real_observation_per_depth_bucket() -> None:
    depth = np.linspace(1000.0, 1100.0, 4000, dtype=np.float64)
    values = np.where(np.arange(depth.size) % 2 == 0, 1.0, 99.0).astype(np.float64)
    maximum = 240

    selected_values, selected_depth = select_gas_scatter_samples(
        depth,
        values,
        1000.0,
        1100.0,
        max_points=maximum,
    )

    assert 0 < selected_depth.size <= maximum
    assert selected_depth.size == selected_values.size
    assert np.all(np.diff(selected_depth) > 0.0)

    normalized = (selected_depth - 1000.0) / 100.0
    buckets = np.minimum(
        maximum - 1,
        np.floor(np.clip(normalized, 0.0, 1.0) * maximum).astype(np.int64),
    )
    assert np.unique(buckets).size == buckets.size
    assert set(np.unique(selected_values)) <= {1.0, 99.0}


def test_ratio_sampler_preserves_all_actual_points_when_density_is_safe() -> None:
    depth = np.asarray([1000.0, 1000.5, 1001.0, 1001.5], dtype=np.float64)
    values = np.asarray([10.0, 20.0, 30.0, 40.0], dtype=np.float64)

    selected_values, selected_depth = select_gas_scatter_samples(
        depth,
        values,
        1000.0,
        1002.0,
        max_points=20,
    )

    assert np.array_equal(selected_depth, depth)
    assert np.array_equal(selected_values, values)
