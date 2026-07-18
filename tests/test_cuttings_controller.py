import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession


def _controller() -> CuttingsController:
    session = ProjectSession()
    session.add_dataset(
        Dataset("data", "Log", DatasetKind.GTI, DepthDomain.MD, np.array([0.0, 1000.0])),
        "Well",
    )
    return CuttingsController(session)


def test_cuttings_interval_stores_percent_composition() -> None:
    controller = _controller()

    sample = controller.add(500, 510, {"sandstone": 70, "clay": 30})

    assert [(item.lithotype_id, item.percentage) for item in sample.components] == [
        ("sandstone", 70.0),
        ("clay", 30.0),
    ]
    assert controller.session.dirty is True


def test_cuttings_requires_hundred_percent_and_non_overlapping_interval() -> None:
    controller = _controller()

    with pytest.raises(ValueError, match="100%"):
        controller.add(500, 510, {"sandstone": 90})
    controller.add(500, 510, {"sandstone": 100})
    with pytest.raises(ValueError, match="пересекается"):
        controller.add(505, 515, {"clay": 100})


def test_sample_analysis_stores_calcimetry_and_lba_in_same_interval() -> None:
    controller = _controller()
    existing = controller.add(500, 510, {"sandstone": 100})

    sample = controller.set_analysis(
        500,
        510,
        calcite_percent=62.5,
        dolomite_percent=17.5,
        lba_group=3,
        lba_type_id="Oil show",
        lba_intensity=4,
        lba_color="yellow-white",
        lba_distribution="spotted",
        lba_cut="Streaming",
        lba_cut_speed="Fast",
        lba_cut_color="Straw",
        lba_residue_type="Good",
        lba_residue_color="Amber",
        lba_odour="Moderate",
        lba_stain="Spotty",
        lba_description="bright direct fluorescence",
    )

    assert sample is existing
    assert len(controller.session.current_well.cuttings) == 1
    assert sample.calcite_percent == 62.5
    assert sample.dolomite_percent == 17.5
    assert sample.insoluble_residue_percent == 20.0
    assert sample.lba_group == 3
    assert sample.lba_type_id == "Oil show"
    assert sample.lba_intensity == 4
    assert sample.lba_color == "yellow-white"
    assert sample.lba_distribution == "spotted"
    assert sample.lba_cut == "Streaming"
    assert sample.lba_cut_speed == "Fast"
    assert sample.lba_cut_color == "Straw"
    assert sample.lba_residue_type == "Good"
    assert sample.lba_residue_color == "Amber"
    assert sample.lba_odour == "Moderate"
    assert sample.lba_stain == "Spotty"
    assert sample.lba_description == "bright direct fluorescence"
    assert controller.session.dirty is True


def test_cuttings_composition_can_be_added_after_interval_analysis() -> None:
    controller = _controller()
    sample = controller.set_analysis(500, 510, calcite_percent=60.0)

    updated = controller.add(500, 510, {"sandstone": 70, "clay": 30})

    assert updated is sample
    assert len(controller.session.current_well.cuttings) == 1
    assert [(item.lithotype_id, item.percentage) for item in updated.components] == [
        ("sandstone", 70.0),
        ("clay", 30.0),
    ]
    assert updated.calcite_percent == 60.0
    assert updated.insoluble_residue_percent is None


def test_sample_analysis_validates_percentages_intensity_and_empty_input() -> None:
    controller = _controller()

    with pytest.raises(ValueError, match="не должна превышать"):
        controller.set_analysis(500, 510, calcite_percent=70, dolomite_percent=40)
    with pytest.raises(ValueError, match="от 1 до 5"):
        controller.set_analysis(500, 510, lba_intensity=6)
    with pytest.raises(ValueError, match="Группа ЛБА"):
        controller.set_analysis(500, 510, lba_group=0)
    with pytest.raises(ValueError, match="хотя бы один"):
        controller.set_analysis(500, 510)
