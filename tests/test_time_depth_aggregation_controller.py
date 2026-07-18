import numpy as np

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
from geoworkbench.project.time_depth_aggregation_controller import (
    TimeDepthAggregationController,
)
from geoworkbench.project.time_depth_mapping_controller import TimeDepthMappingController


def make_session() -> ProjectSession:
    dataset = Dataset(
        "dataset", "Log", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 110.0, 130.0])
    )
    dataset.add_index(
        DatasetIndex(
            "time", "TIME", IndexType.RELATIVE_TIME, IndexRole.TIME, "s",
            np.array([0.0, 5.0, 10.0]),
        )
    )
    well = Well("well", "Well", datasets={dataset.dataset_id: dataset})
    return ProjectSession(
        project=Project("project", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
    )


def test_time_depth_aggregation_controller_supports_undo_redo() -> None:
    session = make_session()
    mapping = TimeDepthMappingController(session).save_profile(
        "Mapping", "time", session.current_dataset.active_index_id,  # type: ignore[union-attr]
        TimeDepthAggregationPolicy.MEAN,
    )
    controller = TimeDepthAggregationController(session)
    plan = controller.analyze(mapping.profile_id, 10.0)

    result = controller.create_copy(mapping.profile_id, plan)
    result_id = result.dataset.dataset_id
    assert session.current_dataset_id == result_id

    controller.undo()
    assert result_id not in session.current_well.datasets  # type: ignore[union-attr]
    assert session.current_dataset_id == "dataset"

    controller.redo()
    assert result_id in session.current_well.datasets  # type: ignore[union-attr]
    assert session.current_dataset_id == result_id
