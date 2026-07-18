from geoworkbench.domain.models import CuttingsSample
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.sample_analysis_dialog import SampleAnalysisDialog


def test_sample_analysis_dialog_keeps_absent_values_unset(qapp) -> None:
    dialog = SampleAnalysisDialog(500.0, 510.0, language=AppLanguage.EN)

    values = dialog.values()

    assert dialog.windowTitle() == "Sample analysis — 500–510 м"
    assert values["calcite_percent"] is None
    assert values["dolomite_percent"] is None
    assert values["lba_group"] is None
    assert values["lba_intensity"] is None
    dialog.close()


def test_sample_analysis_dialog_loads_existing_interval(qapp) -> None:
    sample = CuttingsSample(
        "sample",
        500.0,
        510.0,
        calcite_percent=65.5,
        dolomite_percent=20.0,
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
        lba_description="bright fluorescence",
    )

    dialog = SampleAnalysisDialog(
        500.0,
        510.0,
        language=AppLanguage.RU,
        sample=sample,
    )

    assert dialog.values() == {
        "calcite_percent": 65.5,
        "dolomite_percent": 20.0,
        "lba_group": 3,
        "lba_type_id": "Oil show",
        "lba_intensity": 4,
        "lba_color": "yellow-white",
        "lba_distribution": "spotted",
        "lba_cut": "Streaming",
        "lba_cut_speed": "Fast",
        "lba_cut_color": "Straw",
        "lba_residue_type": "Good",
        "lba_residue_color": "Amber",
        "lba_odour": "Moderate",
        "lba_stain": "Spotty",
        "lba_description": "bright fluorescence",
    }
    dialog.close()
