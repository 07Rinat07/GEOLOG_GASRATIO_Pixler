import numpy as np
import pytest

from geoworkbench.domain.models import CurveData, CurveMetadata
from geoworkbench.services.edit_history import (
    CurveEditCommand,
    CurveEditConflictError,
    CurveEditHistory,
)


def make_curve() -> CurveData:
    return CurveData(
        CurveMetadata("curve-1", "ROP", "ROP", "m/h", None, "dataset-1"),
        np.array([10.0, 20.0, 30.0, 40.0]),
    )


def test_history_executes_undoes_and_redoes_curve_edit() -> None:
    curve = make_curve()
    history = CurveEditHistory()
    command = CurveEditCommand.create(
        curve,
        np.array([1, 2]),
        np.array([25.0, 35.0]),
        description="Карандаш ROP",
    )

    history.execute(command)
    np.testing.assert_allclose(curve.values, [10.0, 25.0, 35.0, 40.0])
    assert curve.version == 2
    assert history.can_undo is True
    assert history.can_redo is False

    assert history.undo() is command
    np.testing.assert_allclose(curve.values, [10.0, 20.0, 30.0, 40.0])
    assert curve.version == 3
    assert history.can_redo is True

    assert history.redo() is command
    np.testing.assert_allclose(curve.values, [10.0, 25.0, 35.0, 40.0])
    assert curve.version == 4


def test_new_command_clears_redo_stack() -> None:
    curve = make_curve()
    history = CurveEditHistory()
    history.execute(CurveEditCommand.create(curve, np.array([0]), np.array([11.0])))
    history.undo()

    history.execute(CurveEditCommand.create(curve, np.array([3]), np.array([44.0])))

    assert history.can_redo is False
    with pytest.raises(RuntimeError, match="Нет команд"):
        history.redo()


def test_command_detects_external_curve_change_before_undo() -> None:
    curve = make_curve()
    history = CurveEditHistory()
    history.execute(CurveEditCommand.create(curve, np.array([1]), np.array([22.0])))
    curve.values[1] = 999.0

    with pytest.raises(CurveEditConflictError, match="вне истории"):
        history.undo()

    assert history.can_undo is True


@pytest.mark.parametrize(
    ("indices", "values", "error"),
    [
        (np.array([], dtype=np.int64), np.array([]), ValueError),
        (np.array([1, 1]), np.array([2.0, 3.0]), ValueError),
        (np.array([1, 2]), np.array([2.0]), ValueError),
        (np.array([-1]), np.array([2.0]), IndexError),
        (np.array([99]), np.array([2.0]), IndexError),
    ],
)
def test_command_rejects_invalid_edits(indices, values, error) -> None:
    with pytest.raises(error):
        CurveEditCommand.create(make_curve(), indices, values)


def test_history_rejects_invalid_limit_and_empty_operations() -> None:
    with pytest.raises(ValueError):
        CurveEditHistory(max_commands=0)

    history = CurveEditHistory()
    with pytest.raises(RuntimeError, match="отмены"):
        history.undo()
    with pytest.raises(RuntimeError, match="повтора"):
        history.redo()
