import numpy as np
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QPushButton

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.project.las_range_editor import LasRangeEditingController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
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


def test_table_range_fill_and_undo_use_selected_cells(qapp, monkeypatch) -> None:
    editor, dataset = make_editor()
    editor.set_dataset(dataset)
    model = editor.model
    selection = editor.table.selectionModel()
    c1_column = next(
        column
        for column in range(model.columnCount())
        if str(model.headerData(column, Qt.Orientation.Horizontal)).startswith("C1")
    )
    for row in (1, 2):
        selection.select(
            model.index(row, c1_column),
            QItemSelectionModel.SelectionFlag.Select,
        )
    monkeypatch.setattr(
        "geoworkbench.ui.las_table_editor.QInputDialog.getDouble",
        lambda *args, **kwargs: (25.0, True),
    )

    editor.fill_constant()

    np.testing.assert_allclose(dataset.curves["c1"].values, [10, 25, 25])
    total = dataset.curve_by_mnemonic("TG_CALC")
    assert total is not None
    np.testing.assert_allclose(total.values, [13, 28, 28])
    editor.undo()
    np.testing.assert_allclose(dataset.curves["c1"].values, [10, 10, 10])
    editor.close()


def test_table_copy_and_paste_selected_interval(qapp) -> None:
    editor, dataset = make_editor()
    editor.set_dataset(dataset)
    model = editor.model
    selection = editor.table.selectionModel()
    c1_column = next(
        column
        for column in range(model.columnCount())
        if str(model.headerData(column, Qt.Orientation.Horizontal)).startswith("C1")
    )
    dataset.curves["c1"].values[:] = [1, 2, 3]
    for row in (0, 1):
        selection.select(model.index(row, c1_column), QItemSelectionModel.SelectionFlag.Select)
    editor.copy_selection()
    selection.clearSelection()
    selection.select(model.index(1, c1_column), QItemSelectionModel.SelectionFlag.Select)

    editor.paste_selection()

    np.testing.assert_allclose(dataset.curves["c1"].values, [1, 1, 2])
    editor.close()


def test_table_editor_uses_english_catalog(qapp) -> None:
    editor, dataset = make_editor()
    english = LasTableEditor(editor.controller, language=AppLanguage.EN)
    english.set_dataset(dataset)
    labels = {button.text() for button in english.findChildren(QPushButton)}
    errors: list[str] = []
    english.edit_failed.connect(errors.append)

    english.paste_selection()

    assert english.hint.text().startswith("Double-click")
    assert {"Fill with value", "Fill with noise", "Copy interval", "Paste"} <= labels
    assert errors == ["Copy an interval first"]
    english.close()
    editor.close()
