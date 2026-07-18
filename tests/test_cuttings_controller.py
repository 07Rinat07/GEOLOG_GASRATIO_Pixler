import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession


def _controller() -> CuttingsController:
    session = ProjectSession()
    session.add_dataset(
        Dataset("data", "Log", DatasetKind.GTI, DepthDomain.MD, np.array([0.0, 1000.0])),
        "Well",
    )
    return CuttingsController(session)


def test_cuttings_interval_stores_percent_composition() -> None:
    controller = _controller()

    sample = controller.add(500, 510, {"sandstone": 70, "clay": 30})

    assert [(item.lithotype_id, item.percentage) for item in sample.components] == [
        ("sandstone", 70.0),
        ("clay", 30.0),
    ]
    assert controller.session.dirty is True


def test_cuttings_requires_hundred_percent_and_non_overlapping_interval() -> None:
    controller = _controller()

    with pytest.raises(ValueError, match="100%"):
        controller.add(500, 510, {"sandstone": 90})
    controller.add(500, 510, {"sandstone": 100})
    with pytest.raises(ValueError, match="пересекается"):
        controller.add(505, 515, {"clay": 100})
