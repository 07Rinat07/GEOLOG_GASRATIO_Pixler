import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.depth_axis_controller import DepthAxisController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.depth_axis import DepthDirection


def test_controller_adds_ascending_copy_without_replacing_source() -> None:
    session = ProjectSession()
    source = Dataset(
        "source", "GIS", DatasetKind.GIS, DepthDomain.MD, np.array([2.0, 1.0, 0.0])
    )
    well = session.add_dataset(source)
    session.dirty = False
    controller = DepthAxisController(session)

    assert controller.analyze_current().direction is DepthDirection.DESCENDING
    result = controller.create_ascending_copy()

    assert set(well.datasets) == {"source", result.dataset_id}
    assert session.current_dataset is result
    assert session.dirty is True
    np.testing.assert_allclose(source.depth, [2.0, 1.0, 0.0])
