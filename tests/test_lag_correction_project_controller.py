import numpy as np
import pytest

from geoworkbench.domain.lag_correction import (
    ConstantTimeLagParameters,
    LagCorrectionAxisMode,
    LagCorrectionMethod,
    LagCorrectionTarget,
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
    Project,
    TimeDepthAggregationPolicy,
    Well,
)
from geoworkbench.project.lag_correction_controller import (
    LagCorrectionProjectController,
    LagCorrectionSourceDatasetMissingError,
)
from geoworkbench.project.session import ProjectSession


def make_session() -> ProjectSession:
    dataset = Dataset(
        "source",
        "Source",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([10.0, 20.0, 30.0]),
    )
    dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 10.0, 20.0]),
        )
    )
    dataset.curves["gas"] = CurveData(
        CurveMetadata("gas", "TGAS", "TGAS", "%", None, "source"),
        np.array([1.0, 2.0, 3.0]),
    )
    well = Well("well", "Well", datasets={"source": dataset})
    return ProjectSession(
        Project("project", "Project", wells={"well": well}),
        "well",
        "source",
    )


def test_project_controller_marks_dirty_and_selects_projection() -> None:
    session = make_session()
    controller = LagCorrectionProjectController(session)
    profile = controller.create_profile(
        name="Gas lag",
        target=LagCorrectionTarget.GAS,
        source_time_index_id="time",
        source_depth_index_id="source:primary-index",
        target_curve_ids=("gas",),
        method=LagCorrectionMethod.CONSTANT_TIME,
        parameters=ConstantTimeLagParameters(10.0),
        aggregation_policy=TimeDepthAggregationPolicy.ERROR,
        created_at="2026-07-23T10:00:00Z",
        created_by="Rinat",
    )

    assert session.dirty
    session.dirty = False
    selection = controller.select_projection(profile.profile_id, LagCorrectionAxisMode.SOURCE)
    assert session.current_dataset_id == selection.dataset.dataset_id
    assert selection.dataset.active_index_id == selection.index_id
    assert session.dirty

    updated = controller.add_revision(
        profile.profile_id,
        source_time_index_id="time",
        source_depth_index_id="source:primary-index",
        target_curve_ids=("gas",),
        method=LagCorrectionMethod.CONSTANT_TIME,
        parameters=ConstantTimeLagParameters(0.0),
        aggregation_policy=TimeDepthAggregationPolicy.ERROR,
        created_at="2026-07-23T11:00:00Z",
        created_by="Rinat",
        expected_latest_revision=1,
    )
    assert updated.latest_revision == 2

    controller.activate_revision(profile.profile_id, 1, expected_active_revision=2)
    assert session.current_well.lag_correction_profiles[profile.profile_id].active_revision == 1


def _projection_dataset(
    dataset_id: str,
    *,
    source_dataset_id: str,
) -> Dataset:
    dataset = Dataset(
        dataset_id,
        dataset_id.title(),
        DatasetKind.DERIVED,
        DepthDomain.MD,
        np.array([10.0, 20.0, 30.0]),
    )
    dataset.headers["LAG_SOURCE_DATASET_ID"] = source_dataset_id
    return dataset


def test_dialog_selection_uses_source_and_restores_projection() -> None:
    session = make_session()
    well = session.current_well
    assert well is not None
    projection = _projection_dataset("projection", source_dataset_id="source")
    well.datasets[projection.dataset_id] = projection
    session.current_dataset_id = projection.dataset_id
    controller = LagCorrectionProjectController(session)

    selection = controller.prepare_dialog_selection()

    assert selection.dataset.dataset_id == "source"
    assert selection.restore_dataset_id == projection.dataset_id
    assert session.current_dataset_id == "source"

    controller.restore_dialog_selection(selection)

    assert session.current_dataset_id == projection.dataset_id


def test_dialog_selection_does_not_override_a_new_selection() -> None:
    session = make_session()
    well = session.current_well
    assert well is not None
    projection = _projection_dataset("projection", source_dataset_id="source")
    other = Dataset(
        "other",
        "Other",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([10.0, 20.0, 30.0]),
    )
    well.datasets[projection.dataset_id] = projection
    well.datasets[other.dataset_id] = other
    session.current_dataset_id = projection.dataset_id
    controller = LagCorrectionProjectController(session)

    selection = controller.prepare_dialog_selection()
    session.current_dataset_id = other.dataset_id
    controller.restore_dialog_selection(selection)

    assert session.current_dataset_id == other.dataset_id


def test_dialog_selection_rejects_missing_projection_source() -> None:
    session = make_session()
    well = session.current_well
    assert well is not None
    projection = _projection_dataset("projection", source_dataset_id="missing-source")
    well.datasets[projection.dataset_id] = projection
    session.current_dataset_id = projection.dataset_id

    with pytest.raises(LagCorrectionSourceDatasetMissingError, match="missing-source"):
        LagCorrectionProjectController(session).prepare_dialog_selection()
