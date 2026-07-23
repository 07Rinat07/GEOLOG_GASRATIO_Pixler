from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.domain.lag_correction import (
    AnnularVolumeFlowLagParameters,
    ConstantTimeLagParameters,
    ControlPointLagParameters,
    LagCorrectionAxisMode,
    LagCorrectionMethod,
    LagCorrectionTarget,
    LagDepthControlPoint,
    PumpStrokeLagParameters,
    lag_seconds,
)
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    TimeDepthAggregationPolicy,
    Well,
)
from geoworkbench.services.lag_correction import (
    LagCorrectionConflictError,
    LagCorrectionController,
    LagCorrectionCreateRequest,
)
from geoworkbench.services.report_definition import (
    ReportDefinition,
    ReportIntervalMode,
    ReportIntervalSelection,
    ReportProfile,
    resolve_report_definition,
)


def make_source() -> Dataset:
    depth = np.array([100.0, 110.0, 120.0, 130.0, 140.0])
    dataset = Dataset("source", "Surface gas", DatasetKind.GTI, DepthDomain.MD, depth)
    dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 10.0, 20.0, 30.0, 40.0]),
        )
    )
    dataset.curves["gas"] = CurveData(
        CurveMetadata("gas", "TGAS", "TGAS", "%", "Total gas", dataset.dataset_id),
        np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
    )
    dataset.curves["rop"] = CurveData(
        CurveMetadata("rop", "ROP", "ROP", "m/h", "ROP", dataset.dataset_id),
        np.array([10.0, 10.0, 9.0, 8.0, 7.0]),
    )
    return dataset


def request(*, profile_id: str = "lag", output: str = "corrected", lag: float = 10.0):
    return LagCorrectionCreateRequest(
        profile_id=profile_id,
        name="Gas lag",
        target=LagCorrectionTarget.GAS,
        source_dataset_id="source",
        source_time_index_id="time",
        source_depth_index_id="source:primary-index",
        target_curve_ids=("gas",),
        method=LagCorrectionMethod.CONSTANT_TIME,
        parameters=ConstantTimeLagParameters(lag),
        aggregation_policy=TimeDepthAggregationPolicy.ERROR,
        output_dataset_id=output,
        output_source_index_id=f"{output}:source",
        output_index_id=f"{output}:corrected",
        created_at="2026-07-23T10:00:00Z",
        created_by="Rinat",
        comment="Initial correction",
    )


def test_constant_lag_creates_dual_axis_without_mutating_source() -> None:
    source = make_source()
    snapshot = deepcopy(source)
    well = Well("well", "Well", datasets={source.dataset_id: source})

    profile = LagCorrectionController(well).create_profile(request())
    output = well.datasets[profile.active.output_dataset_id]

    np.testing.assert_allclose(
        output.indexes[profile.active.output_source_index_id].values,
        [100.0, 110.0, 120.0, 130.0, 140.0],
    )
    np.testing.assert_allclose(
        output.indexes[profile.active.output_index_id].values,
        [np.nan, 100.0, 110.0, 120.0, 130.0],
        equal_nan=True,
    )
    np.testing.assert_allclose(output.curves["gas"].values, source.curves["gas"].values)
    assert set(output.curves) == {"gas"}
    assert output.active_index_id == profile.active.output_index_id
    np.testing.assert_array_equal(source.depth, snapshot.depth)
    np.testing.assert_array_equal(source.indexes["time"].values, snapshot.indexes["time"].values)
    np.testing.assert_array_equal(source.curves["gas"].values, snapshot.curves["gas"].values)


def test_volume_flow_and_pump_strokes_have_explicit_formula() -> None:
    assert lag_seconds(AnnularVolumeFlowLagParameters(12.0, 0.2)) == 60.0
    assert lag_seconds(PumpStrokeLagParameters(12.0, 0.02, 60.0)) == 600.0
    assert lag_seconds(ConstantTimeLagParameters(0.0)) == 0.0


def test_manual_control_points_interpolate_only_inside_control_range() -> None:
    source = make_source()
    well = Well("well", "Well", datasets={source.dataset_id: source})
    raw = request()
    manual = replace(
        raw,
        source_time_index_id=None,
        method=LagCorrectionMethod.CONTROL_POINTS,
        parameters=ControlPointLagParameters(
            (LagDepthControlPoint(1, 95.0), LagDepthControlPoint(3, 125.0))
        ),
    )

    profile = LagCorrectionController(well).create_profile(manual)
    corrected = well.datasets["corrected"].indexes[profile.active.output_index_id].values

    np.testing.assert_allclose(corrected, [np.nan, 95.0, 110.0, 125.0, np.nan], equal_nan=True)


def test_revisions_are_immutable_and_active_revision_can_be_rolled_back() -> None:
    source = make_source()
    well = Well("well", "Well", datasets={source.dataset_id: source})
    controller = LagCorrectionController(well)
    first = controller.create_profile(request())
    second_request = request(output="corrected-v2", lag=20.0)

    second = controller.add_revision(
        first.profile_id,
        second_request,
        expected_latest_revision=1,
    )

    assert second.latest_revision == 2
    assert second.active_revision == 2
    assert "corrected" in well.datasets and "corrected-v2" in well.datasets
    controller.activate_revision("lag", 1, expected_active_revision=2)
    assert well.lag_correction_profiles["lag"].active_revision == 1
    with pytest.raises(LagCorrectionConflictError, match="Revision conflict"):
        controller.add_revision("lag", request(output="v3"), expected_latest_revision=1)


def test_source_prefix_remains_valid_after_append_but_mutation_is_rejected() -> None:
    source = make_source()
    well = Well("well", "Well", datasets={source.dataset_id: source})
    controller = LagCorrectionController(well)
    controller.create_profile(request())

    source.depth = np.append(source.depth, 150.0)
    source.indexes[source.active_index_id].values = np.append(
        source.indexes[source.active_index_id].values, 150.0
    )
    source.indexes["time"].values = np.append(source.indexes["time"].values, 50.0)
    for curve in source.curves.values():
        curve.values = np.append(curve.values, 6.0)
    controller.verify_profile("lag")

    source.curves["gas"].values[1] = 999.0
    with pytest.raises(LagCorrectionConflictError, match="Source prefix"):
        controller.verify_profile("lag")


def test_tampered_materialized_projection_is_rejected() -> None:
    source = make_source()
    well = Well("well", "Well", datasets={source.dataset_id: source})
    controller = LagCorrectionController(well)
    controller.create_profile(request())
    well.datasets["corrected"].curves["gas"].values[0] = 77.0

    with pytest.raises(LagCorrectionConflictError, match="Output dataset"):
        controller.verify_profile("lag")


def test_preview_and_report_explicitly_choose_source_or_corrected_axis() -> None:
    source = make_source()
    well = Well("well", "Well", datasets={source.dataset_id: source})
    controller = LagCorrectionController(well)
    profile = controller.create_profile(request())
    preview = controller.preview(profile.profile_id)

    assert preview.row_count == 5
    assert preview.valid_count == 4
    assert preview.invalid_count == 1
    source_selection = controller.select_axis("lag", LagCorrectionAxisMode.SOURCE)
    corrected_selection = controller.select_axis("lag", LagCorrectionAxisMode.CORRECTED)
    assert source_selection.dataset is corrected_selection.dataset
    assert source_selection.index_id != corrected_selection.index_id

    source_report = resolve_report_definition(
        source_selection.dataset,
        ReportDefinition(
            "source-report",
            "Source axis",
            ReportProfile.GAS,
            source_selection.dataset.dataset_id,
            source_selection.index_id,
            ReportIntervalSelection(ReportIntervalMode.CUSTOM, 100.0, 120.0),
            curve_ids=("gas",),
        ),
    )
    corrected_report = resolve_report_definition(
        corrected_selection.dataset,
        ReportDefinition(
            "corrected-report",
            "Corrected axis",
            ReportProfile.GAS,
            corrected_selection.dataset.dataset_id,
            corrected_selection.index_id,
            ReportIntervalSelection(ReportIntervalMode.CUSTOM, 100.0, 120.0),
            curve_ids=("gas",),
        ),
    )

    assert source_report.interval.indices.tolist() == [0, 1, 2]
    assert corrected_report.interval.indices.tolist() == [1, 2, 3]


def test_duplicate_time_requires_explicit_aggregation_policy() -> None:
    source = make_source()
    source.indexes["time"].values[2] = 10.0
    source.depth[2] = 125.0
    source.indexes[source.active_index_id].values[2] = 125.0
    well = Well("well", "Well", datasets={source.dataset_id: source})

    with pytest.raises(LagCorrectionConflictError, match="неоднозначен"):
        LagCorrectionController(well).create_profile(request(lag=0.0))

    raw = request(output="mean", lag=0.0)
    mean_request = replace(raw, aggregation_policy=TimeDepthAggregationPolicy.MEAN)
    profile = LagCorrectionController(well).create_profile(mean_request)
    corrected = well.datasets["mean"].indexes[profile.active.output_index_id].values
    assert corrected[1] == pytest.approx(117.5)
    assert corrected[2] == pytest.approx(117.5)


def test_invalid_time_unit_and_control_point_range_are_rejected() -> None:
    source = make_source()
    source.indexes["time"].unit = "ms"
    well = Well("well", "Well", datasets={source.dataset_id: source})
    with pytest.raises(LagCorrectionConflictError, match="не распознана"):
        LagCorrectionController(well).create_profile(request())

    source = make_source()
    well = Well("well", "Well", datasets={source.dataset_id: source})
    raw = request()
    manual = replace(
        raw,
        source_time_index_id=None,
        method=LagCorrectionMethod.CONTROL_POINTS,
        parameters=ControlPointLagParameters(
            (LagDepthControlPoint(0, 90.0), LagDepthControlPoint(5, 150.0))
        ),
    )
    with pytest.raises(LagCorrectionConflictError, match="выходит"):
        LagCorrectionController(well).create_profile(manual)
