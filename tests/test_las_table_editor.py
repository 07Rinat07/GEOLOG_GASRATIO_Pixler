import numpy as np
from PySide6.QtCore import Qt

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.project.las_range_editor import LasRangeEditingController
from geoworkbench.project.session import ProjectSession
from geoworkbench.ui.las_table_editor import LasTableEditor


def make_editor() -> tuple[LasTableEditor, Dataset]:
    dataset = Dataset(
        "dataset",
        "LAS",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]),
    )
    for mnemonic, values in (("C1", [10, 10, 10]), ("C2", [2, 2, 2]), ("C3", [1, 1, 1])):
        curve_id = mnemonic.lower()
        dataset.curves[curve_id] = CurveData(
            CurveMetadata(curve_id, mnemonic, mnemonic, "%", None, dataset.dataset_id),
            np.asarray(values, dtype=np.float64),
        )
    session = ProjectSession()
    session.add_dataset(dataset)
    session.calculate_basic_gas_ratios()
    return LasTableEditor(LasRangeEditingController(session)), dataset


def test_table_model_edits_source_value_and_recalculates_outputs(qapp) -> None:
    editor, dataset = make_editor()
    editor.set_dataset(dataset)
    model = editor.model
    c1_column = next(
        column
        for column in range(model.columnCount())
        if str(model.headerData(column, Qt.Orientation.Horizontal)).startswith("C1")
    )
    edited: list[bool] = []
    model.dataset_edited.connect(lambda: edited.append(True))

    assert model.setData(model.index(1, c1_column), "20,5") is True

    assert dataset.curves["c1"].values[1] == 20.5
    total = dataset.curve_by_mnemonic("TG_CALC")
    assert total is not None
    assert total.values[1] == 23.5
    assert edited == [True]
    editor.close()


def test_table_model_keeps_depth_and_calculated_curves_read_only(qapp) -> None:
    editor, dataset = make_editor()
    editor.set_dataset(dataset)
    model = editor.model
    total_column = next(
        column
        for column in range(model.columnCount())
        if str(model.headerData(column, Qt.Orientation.Horizontal)).startswith("TG_CALC")
    )

    assert not (model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable)
    assert not (model.flags(model.index(0, total_column)) & Qt.ItemFlag.ItemIsEditable)
    editor.close()
