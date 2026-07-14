import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.lithology_controller import LithologyController
from geoworkbench.project.session import ProjectSession


def make_controller() -> LithologyController:
    dataset = Dataset("dataset", "Well", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 200.0]))
    session = ProjectSession()
    session.add_dataset(dataset)
    session.dirty = False
    return LithologyController(session)


def test_lithology_controller_crud_and_adjacent_intervals() -> None:
    controller = make_controller()
    first = controller.add(100.0, 150.0, "sandstone", description="Песчаник")
    second = controller.add(150.0, 200.0, "claystone")

    assert controller.available() == (first, second)
    controller.update(
        first.interval_id,
        top_depth=100.0,
        bottom_depth=140.0,
        lithotype_id="siltstone",
        description="Алевролит",
    )
    assert first.bottom_depth == 140.0
    assert first.lithotype_id == "siltstone"
    assert controller.remove(second.interval_id) is second
    assert controller.available() == (first,)
    assert controller.session.dirty is True


def test_lithology_controller_rejects_overlap_and_out_of_range() -> None:
    controller = make_controller()
    controller.add(120.0, 160.0, "sandstone")

    with pytest.raises(ValueError, match="пересекается"):
        controller.add(150.0, 170.0, "claystone")
    with pytest.raises(ValueError, match="диапазон"):
        controller.add(90.0, 110.0, "claystone")
    with pytest.raises(ValueError, match="меньше"):
        controller.add(180.0, 170.0, "claystone")
