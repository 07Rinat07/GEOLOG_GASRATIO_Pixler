import numpy as np
import pytest

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
from geoworkbench.project.curve_metadata_controller import CurveMetadataController
from geoworkbench.project.session import ProjectSession


def make_controller() -> CurveMetadataController:
    session = ProjectSession()
    dataset = Dataset(
        "dataset-1",
        "Logging",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    dataset.curves["c1"] = CurveData(
        CurveMetadata("c1", "CH4", "C1", "%", "Methane", dataset.dataset_id),
        np.array([1.0, 2.0]),
    )
    dataset.curves["c2"] = CurveData(
        CurveMetadata("c2", "C2", "C2", "%", "Ethane", dataset.dataset_id),
        np.array([0.5, 0.7]),
    )
    dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 1.0]),
        )
    )
    session.add_dataset(dataset)
    session.dirty = False
    return CurveMetadataController(session)


def test_updates_metadata_preserves_canonical_identity_and_supports_history() -> None:
    controller = make_controller()

    controller.update("c1", mnemonic="methane", unit="ppm", description="Total methane")

    curve = controller.session.current_dataset.curves["c1"]  # type: ignore[union-attr]
    assert curve.metadata.original_mnemonic == "METHANE"
    assert curve.metadata.canonical_mnemonic == "C1"
    assert curve.metadata.unit == "ppm"
    assert controller.session.dirty

    controller.undo()
    assert curve.metadata.original_mnemonic == "CH4"
    controller.redo()
    assert curve.metadata.original_mnemonic == "METHANE"


@pytest.mark.parametrize("mnemonic", ["DEPT", "TIME"])
def test_rejects_index_mnemonics(mnemonic: str) -> None:
    controller = make_controller()

    with pytest.raises(ValueError, match="индексом"):
        controller.update("c1", mnemonic=mnemonic, unit="%", description="Methane")


def test_rejects_duplicate_invalid_mnemonic_and_unit() -> None:
    controller = make_controller()

    with pytest.raises(ValueError, match="уже существует"):
        controller.update("c1", mnemonic="c2", unit="%", description="Methane")
    with pytest.raises(ValueError, match="Мнемоника"):
        controller.update("c1", mnemonic="bad name", unit="%", description="Methane")
    with pytest.raises(ValueError, match="пробелы"):
        controller.update("c1", mnemonic="CH4", unit="mg / l", description="Methane")


def test_empty_unit_and_description_are_normalized_to_none() -> None:
    controller = make_controller()

    controller.update("c1", mnemonic="CH4", unit=" ", description=" ")

    metadata = controller.session.current_dataset.curves["c1"].metadata  # type: ignore[union-attr]
    assert metadata.unit is None
    assert metadata.description is None


def test_history_detects_external_metadata_change() -> None:
    controller = make_controller()
    controller.update("c1", mnemonic="METHANE", unit="%", description="Methane")
    curve = controller.session.current_dataset.curves["c1"]  # type: ignore[union-attr]
    curve.metadata = CurveMetadata("c1", "OTHER", "C1", "%", None, "dataset-1")

    with pytest.raises(RuntimeError, match="вне истории"):
        controller.undo()


def test_create_curve_initializes_missing_values_and_supports_undo_redo() -> None:
    controller = make_controller()

    curve = controller.create(mnemonic="rop", unit="m/h", description="Penetration rate")

    dataset = controller.session.current_dataset
    assert dataset is not None
    assert dataset.curves[curve.metadata.curve_id] is curve
    assert curve.metadata.original_mnemonic == "ROP"
    assert curve.metadata.provenance == "user"
    assert np.isnan(curve.values).all()
    controller.undo()
    assert curve.metadata.curve_id not in dataset.curves
    controller.redo()
    assert dataset.curves[curve.metadata.curve_id] is curve


def test_create_curve_rejects_export_index_and_undo_after_value_edit() -> None:
    controller = make_controller()
    with pytest.raises(ValueError, match="индексом"):
        controller.create(mnemonic="DEPT", unit="m", description="Reserved")

    curve = controller.create(mnemonic="ROP", unit="m/h", description="Rate")
    curve.values[0] = 10.0
    curve.version += 1
    with pytest.raises(RuntimeError, match="пользовательские правки"):
        controller.undo()
