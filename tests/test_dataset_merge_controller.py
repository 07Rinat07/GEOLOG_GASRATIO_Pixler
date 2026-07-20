import numpy as np
import pytest

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.project.dataset_merge_controller import DatasetMergeController
from geoworkbench.project.session import ProjectSession
from geoworkbench.tablet.models import TabletLayout


def make_controller() -> tuple[DatasetMergeController, Dataset, Dataset]:
    session = ProjectSession()
    source = Dataset("source", "Source", DatasetKind.GIS, DepthDomain.MD, np.array([100.0, 101.0]))
    source.curves["gr"] = CurveData(
        CurveMetadata("gr", "GR", "GR", "API", None, source.dataset_id),
        np.array([10.0, 11.0]),
    )
    target = Dataset("target", "Target", DatasetKind.GTI, DepthDomain.MD, np.array([101.0, 102.0]))
    target.curves["rop"] = CurveData(
        CurveMetadata("rop", "ROP", "ROP", "m/h", None, target.dataset_id),
        np.array([20.0, 21.0]),
    )
    session.add_dataset(source)
    session.add_dataset(target)
    session.dirty = False
    return DatasetMergeController(session), source, target


def test_merge_controller_creates_copy_and_supports_undo_redo() -> None:
    controller, source, target = make_controller()

    result = controller.create(source.dataset_id, controller.analyze(source.dataset_id))

    well = controller.session.current_well
    assert well is not None
    assert controller.session.current_dataset is result
    assert set(well.datasets) == {"source", "target", result.dataset_id}
    layout = TabletLayout()
    controller.session.tablet_layouts[result.dataset_id] = layout
    controller.undo()
    assert controller.session.current_dataset is target
    assert set(well.datasets) == {"source", "target"}
    assert result.dataset_id not in controller.session.tablet_layouts
    assert controller.redo() is result
    assert controller.session.current_dataset is result
    assert controller.session.tablet_layouts[result.dataset_id] is layout


def test_merge_controller_blocks_undo_after_result_edit() -> None:
    controller, source, _ = make_controller()
    result = controller.create(source.dataset_id, controller.analyze(source.dataset_id))
    result.curve_by_mnemonic("GR").values[0] = 99.0

    with pytest.raises(RuntimeError, match="последующие правки"):
        controller.undo()
