import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.depth_axis_controller import DepthAxisController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.depth_axis import DepthDirection


def test_controller_adds_ascending_copy_without_replacing_source() -> None:
    session = ProjectSession()
    source = Dataset("source", "GIS", DatasetKind.GIS, DepthDomain.MD, np.array([2.0, 1.0, 0.0]))
    well = session.add_dataset(source)
    session.dirty = False
    controller = DepthAxisController(session)

    assert controller.analyze_current().direction is DepthDirection.DESCENDING
    result = controller.create_ascending_copy()

    assert set(well.datasets) == {"source", result.dataset_id}
    assert session.current_dataset is result
    assert session.dirty is True
    np.testing.assert_allclose(source.depth, [2.0, 1.0, 0.0])

    assert controller.can_undo_ascending_copy
    controller.undo_ascending_copy()
    assert session.current_dataset is source
    assert set(well.datasets) == {"source"}
    assert controller.can_redo_ascending_copy

    assert controller.redo_ascending_copy() is result
    assert session.current_dataset is result
    assert set(well.datasets) == {"source", result.dataset_id}


def test_controller_resample_copy_supports_undo_and_redo() -> None:
    session = ProjectSession()
    source = Dataset("source", "LAS", DatasetKind.GTI, DepthDomain.MD, np.array([0.0, 1.0, 2.0]))
    well = session.add_dataset(source)
    controller = DepthAxisController(session)

    plan = controller.analyze_resample(0.0, 2.0, 0.5)
    result = controller.create_resampled_copy(plan)
    assert session.current_dataset is result
    assert set(well.datasets) == {"source", result.dataset_id}

    controller.undo_resample()
    assert session.current_dataset is source
    assert set(well.datasets) == {"source"}

    assert controller.redo_resample() is result
    assert session.current_dataset is result
    assert set(well.datasets) == {"source", result.dataset_id}
