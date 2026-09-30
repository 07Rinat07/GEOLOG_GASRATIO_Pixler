import numpy as np
import pytest

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.project.curve_transfer_controller import CurveTransferController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.edit_history import CommandHistory, CurveEditCommand


def make_controller(
    shared_history: CommandHistory | None = None,
) -> tuple[CurveTransferController, Dataset, Dataset]:
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
    return (
        CurveTransferController(session, shared_history=shared_history),
        source,
        target,
    )


def test_controller_applies_transfer_atomically_and_supports_history() -> None:
    controller, source, target = make_controller()
    analysis = controller.analyze(source.dataset_id)

    curves = controller.apply(source.dataset_id, ("gr",), analysis)

    curve = curves[0]
    assert target.curves[curve.metadata.curve_id] is curve
    assert controller.can_undo
    undone = controller.undo()
    assert curve.metadata.curve_id not in target.curves
    assert undone == curves
    assert controller.can_redo
    redone = controller.redo()
    assert target.curves[curve.metadata.curve_id] is curve
    assert redone == curves


def test_controller_blocks_undo_after_transferred_values_are_edited() -> None:
    controller, source, _ = make_controller()
    curve = controller.apply(source.dataset_id, ("gr",), controller.analyze(source.dataset_id))[0]
    curve.values[0] = 99.0
    curve.version += 1

    with pytest.raises(RuntimeError, match="последующие правки"):
        controller.undo()



def test_shared_history_keeps_transfer_domain_safe_and_allows_undo_after_reverted_edit() -> None:
    history = CommandHistory()
    controller, source, target = make_controller(history)
    curve = controller.apply(
        source.dataset_id,
        ("gr",),
        controller.analyze(source.dataset_id),
    )[0]

    history.execute(
        CurveEditCommand.create(
            curve,
            np.array([0], dtype=np.int64),
            np.array([99.0], dtype=np.float64),
        )
    )

    assert controller.can_undo is False
    assert history.next_undo is not None
    assert history.next_undo.history_domain == "curve"

    history.undo()

    assert controller.can_undo is True
    np.testing.assert_allclose(curve.values, [10.0, 20.0])

    controller.undo()

    assert curve.metadata.curve_id not in target.curves
    assert controller.can_redo is True


def test_shared_history_blocks_transfer_undo_when_metadata_changed_outside_history() -> None:
    history = CommandHistory()
    controller, source, _ = make_controller(history)
    curve = controller.apply(
        source.dataset_id,
        ("gr",),
        controller.analyze(source.dataset_id),
    )[0]
    curve.metadata = CurveMetadata(
        curve.metadata.curve_id,
        curve.metadata.original_mnemonic,
        curve.metadata.canonical_mnemonic,
        "gAPI",
        curve.metadata.description,
        curve.metadata.source_dataset_id,
        provenance=curve.metadata.provenance,
        semantic=curve.metadata.semantic,
    )

    with pytest.raises(RuntimeError, match="последующие правки"):
        controller.undo()

    assert controller.can_undo is True
