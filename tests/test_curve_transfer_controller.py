import numpy as np
import pytest

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.project.curve_transfer_controller import CurveTransferController
from geoworkbench.project.session import ProjectSession


def make_controller() -> tuple[CurveTransferController, Dataset, Dataset]:
    session = ProjectSession()
    source = Dataset("source", "GIS", DatasetKind.GIS, DepthDomain.MD, np.array([100.0, 101.0]))
    source.curves["gr"] = CurveData(
        CurveMetadata("gr", "GR", "GR", "API", None, source.dataset_id),
        np.array([10.0, 20.0]),
    )
    target = Dataset("target", "GTI", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 101.0]))
    session.add_dataset(source)
    session.add_dataset(target)
    session.dirty = False
    return CurveTransferController(session), source, target


def test_controller_applies_transfer_atomically_and_supports_history() -> None:
    controller, source, target = make_controller()
    analysis = controller.analyze(source.dataset_id)

    curves = controller.apply(source.dataset_id, ("gr",), analysis)

    curve = curves[0]
    assert target.curves[curve.metadata.curve_id] is curve
    assert controller.can_undo
    controller.undo()
    assert curve.metadata.curve_id not in target.curves
    assert controller.can_redo
    controller.redo()
    assert target.curves[curve.metadata.curve_id] is curve


def test_controller_blocks_undo_after_transferred_values_are_edited() -> None:
    controller, source, _ = make_controller()
    curve = controller.apply(source.dataset_id, ("gr",), controller.analyze(source.dataset_id))[0]
    curve.values[0] = 99.0
    curve.version += 1

    with pytest.raises(RuntimeError, match="последующие правки"):
        controller.undo()
