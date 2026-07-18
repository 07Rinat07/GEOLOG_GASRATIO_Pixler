import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.stratigraphy_controller import StratigraphyController


def _controller() -> StratigraphyController:
    session = ProjectSession()
    session.add_dataset(
        Dataset("dataset", "Well", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 300.0]))
    )
    session.dirty = False
    return StratigraphyController(session)


def test_stratigraphy_crud_allows_nested_different_ranks() -> None:
    controller = _controller()
    period = controller.add(
        100.0,
        300.0,
        "K",
        rank="System / Period",
        name="Cretaceous",
        color="#7fc64e",
    )
    stage = controller.add(
        150.0,
        200.0,
        "K1a",
        rank="Stage / Age",
        name="Albian",
        description="Reservoir interval",
    )

    assert controller.available() == (period, stage)
    controller.update(
        stage.interval_id,
        top_depth=155.0,
        bottom_depth=205.0,
        code="K1a",
        rank="Stage / Age",
        name="Albian",
        color="#abcdef",
        description="Updated",
    )
    assert stage.top_depth == 155.0
    assert stage.color == "#abcdef"
    assert controller.remove(period.interval_id) is period
    assert controller.session.dirty is True


def test_stratigraphy_rejects_overlap_within_same_rank_and_invalid_values() -> None:
    controller = _controller()
    controller.add(100.0, 180.0, "K1", rank="Series / Epoch")

    with pytest.raises(ValueError, match="того же ранга"):
        controller.add(170.0, 200.0, "K2", rank="Series / Epoch")
    with pytest.raises(ValueError, match="диапазон"):
        controller.add(90.0, 110.0, "K0", rank="Stage / Age")
    with pytest.raises(ValueError, match="#RRGGBB"):
        controller.add(200.0, 250.0, "K3", color="green")
    with pytest.raises(ValueError, match="меньше"):
        controller.add(250.0, 250.0, "K4")
