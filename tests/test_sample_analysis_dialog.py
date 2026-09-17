from geoworkbench.domain.models import CuttingsSample
from PySide6.QtWidgets import QTabWidget
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
    assert values["lba_description_i18n"] == {}
    assert values["analysis_interpretation_i18n"] == {}
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
        analysis_interpretation="Manual geologist conclusion",
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
        "lba_description_i18n": {},
        "analysis_interpretation": "Manual geologist conclusion",
        "analysis_interpretation_i18n": {},
        "analysis_interpretation_source_language": None,
    }
    dialog.close()


def test_sample_analysis_dialog_edits_all_author_text_languages(qapp) -> None:
    dialog = SampleAnalysisDialog(500.0, 510.0, language=AppLanguage.EN)

    assert dialog.findChild(QTabWidget, "lba-description-language-tabs").count() == 3
    assert dialog.findChild(QTabWidget, "analysis-interpretation-language-tabs").count() == 3
    dialog.lba_description_inputs["ru"].setText("Яркая флуоресценция")
    dialog.lba_description_inputs["kk"].setText("Жарқын флуоресценция")
    dialog.lba_description_inputs["en"].setText("Bright fluorescence")
    dialog.interpretation_inputs["ru"].setPlainText("Признаки нефти")
    dialog.interpretation_inputs["kk"].setPlainText("Мұнай белгілері")
    dialog.interpretation_inputs["en"].setPlainText("Oil show")

    values = dialog.values()
    assert values["lba_description_i18n"] == {
        "ru": "Яркая флуоресценция",
        "kk": "Жарқын флуоресценция",
        "en": "Bright fluorescence",
    }
    assert values["analysis_interpretation_i18n"]["kk"] == "Мұнай белгілері"
    dialog.close()


def test_sample_analysis_dialog_does_not_promote_legacy_fallback(qapp) -> None:
    sample = CuttingsSample(
        "sample",
        500.0,
        510.0,
        lba_description="Legacy LBA",
        analysis_interpretation="Legacy conclusion",
    )
    dialog = SampleAnalysisDialog(
        500.0,
        510.0,
        language=AppLanguage.RU,
        sample=sample,
    )

    values = dialog.values()
    assert values["lba_description_i18n"] == {}
    assert values["analysis_interpretation_i18n"] == {}
    dialog.close()
