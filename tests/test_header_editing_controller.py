import numpy as np
import pytest

from geoworkbench.domain.models import (
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
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
        version_headers={"VERS": "2.0", "WRAP": "NO", "DLM": "SPACE"},
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

    assert [
        (entry.mnemonic, entry.value) for entry in controller.entries(HeaderSection.PARAMETER)
    ] == [("MUD", "OBM")]
    controller.undo()
    assert {entry.mnemonic for entry in controller.entries(HeaderSection.PARAMETER)} == {
        "MUD",
        "RUN",
    }


def test_edits_custom_version_header_and_protects_export_fields() -> None:
    controller = make_controller()

    controller.update(HeaderSection.VERSION, "DLM", "DLM", "COMMA")

    dataset = controller.session.current_dataset
    assert dataset is not None
    assert dataset.version_headers["DLM"] == "COMMA"
    with pytest.raises(ValueError, match="планом экспорта"):
        controller.update(HeaderSection.VERSION, "VERS", "VERS", "1.2")
    with pytest.raises(ValueError, match="планом экспорта"):
        controller.remove(HeaderSection.VERSION, "WRAP")
    controller.undo()
    assert dataset.version_headers["DLM"] == "SPACE"


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


def test_depth_summary_detects_mismatch_and_synchronizes_fields() -> None:
    controller = make_controller()

    summary = controller.depth_summary()
    assert any("STOP" in issue for issue in summary.issues)

    controller.synchronize_depth_fields()

    dataset = controller.session.current_dataset
    assert dataset is not None
    assert dataset.headers["STRT"] == "100"
    assert dataset.headers["STOP"] == "101"
    assert dataset.headers["STEP"] == "1"
    assert not any(
        "STRT=" in issue or "STOP=" in issue for issue in controller.depth_summary().issues
    )
    controller.undo()
    assert "STOP" not in dataset.headers


def test_typed_null_rejects_collision_and_is_reversible() -> None:
    controller = make_controller()

    with pytest.raises(ValueError, match="совпадает"):
        controller.set_null_value(100.0)

    controller.set_null_value(-999.25)
    assert controller.depth_summary().null_value == pytest.approx(-999.25)
    controller.undo()
    assert controller.depth_summary().null_value is None


def test_depth_sync_rejects_non_uniform_index() -> None:
    controller = make_controller()
    dataset = controller.session.current_dataset
    assert dataset is not None
    dataset.depth = np.array([100.0, 101.0, 103.0])

    with pytest.raises(ValueError, match="равномерной"):
        controller.synchronize_depth_fields()


def test_depth_sync_rejects_active_time_index() -> None:
    controller = make_controller()
    dataset = controller.session.current_dataset
    assert dataset is not None
    dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 1.0]),
        ),
        make_active=True,
    )

    with pytest.raises(ValueError, match="глубинный индекс"):
        controller.synchronize_depth_fields()
    assert any("не является глубинным" in issue for issue in controller.depth_summary().issues)
