import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.header_editing_controller import (
    HeaderEditingController,
    HeaderSection,
)
from geoworkbench.project.session import ProjectSession


def make_controller() -> HeaderEditingController:
    session = ProjectSession()
    dataset = Dataset(
        "dataset-1",
        "Logging",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
        headers={"WELL": "Old Well", "STRT": "100", "LAT": "51.2"},
        parameters={"RUN": "1"},
    )
    session.add_dataset(dataset)
    session.dirty = False
    return HeaderEditingController(session)


def test_updates_well_name_and_supports_undo_redo() -> None:
    controller = make_controller()

    controller.update(HeaderSection.WELL, "WELL", "WELL", "New Well")

    assert controller.session.current_well is not None
    assert controller.session.current_well.name == "New Well"
    assert controller.can_undo
    assert controller.session.dirty

    controller.undo()
    assert controller.session.current_well.name == "Old Well"
    controller.redo()
    assert controller.session.current_well.name == "New Well"


def test_add_rename_and_remove_parameter_are_reversible() -> None:
    controller = make_controller()

    controller.add(HeaderSection.PARAMETER, "  mud_type ", " WBM ")
    controller.update(HeaderSection.PARAMETER, "MUD_TYPE", "MUD", "OBM")
    controller.remove(HeaderSection.PARAMETER, "RUN")

    assert [(entry.mnemonic, entry.value) for entry in controller.entries(HeaderSection.PARAMETER)] == [
        ("MUD", "OBM")
    ]
    controller.undo()
    assert {entry.mnemonic for entry in controller.entries(HeaderSection.PARAMETER)} == {"MUD", "RUN"}


@pytest.mark.parametrize("mnemonic", ["STRT", "STOP", "STEP", "NULL"])
def test_depth_and_export_managed_fields_are_protected(mnemonic: str) -> None:
    controller = make_controller()

    with pytest.raises(ValueError, match="глубинные операции"):
        controller.add(HeaderSection.WELL, mnemonic, "1")


@pytest.mark.parametrize(
    ("mnemonic", "value", "message"),
    [("LAT", "91", "Широта"), ("LONG", "-181", "Долгота"), ("LAT", "north", "числом")],
)
def test_validates_decimal_coordinates(mnemonic: str, value: str, message: str) -> None:
    controller = make_controller()

    with pytest.raises(ValueError, match=message):
        controller.update(HeaderSection.WELL, "LAT", mnemonic, value)


def test_rejects_duplicate_and_invalid_mnemonics() -> None:
    controller = make_controller()

    with pytest.raises(ValueError, match="уже существует"):
        controller.add(HeaderSection.WELL, "well", "Duplicate")
    with pytest.raises(ValueError, match="Мнемоника"):
        controller.add(HeaderSection.PARAMETER, "bad name", "value")
