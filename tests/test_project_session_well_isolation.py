import numpy as np

from geoworkbench.domain.models import (
    CuttingsComponent,
    CuttingsSample,
    Dataset,
    DatasetKind,
    DepthDomain,
    LithologyInterval,
    StratigraphyInterval,
)
from geoworkbench.project.session import ProjectSession


def _dataset(dataset_id: str, name: str, well: str) -> Dataset:
    return Dataset(
        dataset_id,
        name,
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1000.0, 1010.0]),
        headers={"WELL": well},
    )


def test_opening_unrelated_las_in_new_well_does_not_reuse_manual_intervals() -> None:
    session = ProjectSession()
    first = _dataset("first", "First LAS", "Well A")
    first_well = session.add_dataset(first, create_new_well=True)
    first_well.lithology.append(LithologyInterval("lith", 1000.0, 1010.0, "sandstone"))
    first_well.cuttings.append(
        CuttingsSample(
            "sample",
            1000.0,
            1010.0,
            [CuttingsComponent("sandstone", 100.0)],
        )
    )
    first_well.stratigraphy.append(
        StratigraphyInterval("strat", 1000.0, 1010.0, "F", "Formation", "formation")
    )

    second = _dataset("second", "Second LAS", "Well B")
    second_well = session.add_dataset(second, create_new_well=True)

    assert second_well is session.current_well
    assert second_well is not first_well
    assert second_well.lithology == []
    assert second_well.cuttings == []
    assert second_well.stratigraphy == []
    assert first_well.lithology
    assert first_well.cuttings
    assert first_well.stratigraphy


def test_new_well_names_are_disambiguated_without_merging_interpretation_state() -> None:
    session = ProjectSession()

    first = session.add_dataset(_dataset("one", "One", "Same Well"), create_new_well=True)
    second = session.add_dataset(_dataset("two", "Two", "Same Well"), create_new_well=True)

    assert first.name == "Same Well"
    assert second.name == "Same Well (2)"
    assert first.well_id != second.well_id
