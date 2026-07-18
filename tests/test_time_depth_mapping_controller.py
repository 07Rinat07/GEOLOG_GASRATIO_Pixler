import numpy as np
import pytest

from geoworkbench.domain.models import (
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
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.time_depth_mapping_controller import TimeDepthMappingController


def make_session() -> ProjectSession:
    dataset = Dataset(
        "dataset", "Log", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 110.0, 130.0])
    )
    dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 10.0, 10.0]),
        )
    )
    well = Well("well", "Well", datasets={dataset.dataset_id: dataset})
    return ProjectSession(
        project=Project("project", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
    )


def test_mapping_profile_lifecycle_and_resolution() -> None:
    session = make_session()
    controller = TimeDepthMappingController(session)

    profile = controller.save_profile(
        "  Повторный проход  ",
        "time",
        session.current_dataset.active_index_id,  # type: ignore[union-attr]
        TimeDepthAggregationPolicy.MEAN,
    )
    match = controller.resolve(profile.profile_id, "10")

    assert profile.name == "Повторный проход"
    assert match.depth == 120.0
    assert match.matched_rows == (1, 2)
    assert session.dirty

    controller.delete_profile(profile.profile_id)
    assert profile.profile_id not in session.project.time_depth_mapping_profiles


def test_mapping_profile_validates_name_indexes_and_dataset_binding() -> None:
    session = make_session()
    controller = TimeDepthMappingController(session)
    depth_id = session.current_dataset.active_index_id  # type: ignore[union-attr]
    controller.save_profile("Profile", "time", depth_id, TimeDepthAggregationPolicy.FIRST)

    with pytest.raises(ValueError, match="уже существует"):
        controller.save_profile("profile", "time", depth_id, TimeDepthAggregationPolicy.LAST)
    with pytest.raises(ValueError, match="роль time"):
        controller.save_profile("Wrong", depth_id, depth_id, TimeDepthAggregationPolicy.FIRST)

    other = Dataset("other", "Other", DatasetKind.GTI, DepthDomain.MD, np.array([1.0]))
    session.current_well.datasets[other.dataset_id] = other  # type: ignore[union-attr]
    session.current_dataset_id = other.dataset_id
    profile_id = next(iter(session.project.time_depth_mapping_profiles))
    with pytest.raises(ValueError, match="другому набору"):
        controller.resolve(profile_id, "10")
