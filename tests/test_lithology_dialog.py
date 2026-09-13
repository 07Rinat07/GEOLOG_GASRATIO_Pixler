import numpy as np
from PySide6.QtWidgets import QDialogButtonBox, QPushButton, QTableWidget

from geoworkbench.domain.models import (
    Dataset,
    DatasetKind,
    DepthDomain,
    LithologyInterval,
    Well,
)
from geoworkbench.project.lithology_controller import LithologyController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.lithology_dialog import LithologyDialog


def test_lithology_dialog_adds_interval(qapp) -> None:
    dataset = Dataset("dataset", "Well", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 200.0]))
    session = ProjectSession()
    session.add_dataset(dataset)
    dialog = LithologyDialog(LithologyController(session))
    dialog.top_input.setValue(100.0)
    dialog.bottom_input.setValue(150.0)
    dialog.lithotype_input.setCurrentIndex(dialog.lithotype_input.findData("sandstone"))
    dialog.description_input.setText("Песчаник")

    dialog._add()

    table = dialog.findChild(QTableWidget, "lithology-intervals-table")
    assert table is not None
    assert table.rowCount() == 1
    assert table.item(0, 2).text() == "sandstone"
    dialog.close()


def test_lithology_dialog_inserts_description_template(qapp) -> None:
    session = ProjectSession()
    session.project.wells["well"] = Well("well", "Well")
    session.current_well_id = "well"
    dialog = LithologyDialog(
        LithologyController(session),
        description_templates=(("Песчаник", "Песчаник серый, мелкозернистый"),),
    )

    dialog.template_input.setCurrentIndex(dialog.template_input.findText("Песчаник"))

    assert dialog.description_input.text() == "Песчаник серый, мелкозернистый"
    dialog.close()


def test_lithology_dialog_offers_factory_templates_in_selected_language(qapp) -> None:
    session = ProjectSession()
    session.project.wells["well"] = Well("well", "Well")
    session.current_well_id = "well"
    dialog = LithologyDialog(LithologyController(session), language=AppLanguage.RU)

    sandstone_lithotype = dialog.lithotype_input.findData("sandstone")
    dialog.lithotype_input.setCurrentIndex(sandstone_lithotype)
    english = dialog.template_language_input.findData(AppLanguage.EN.value)
    dialog.template_language_input.setCurrentIndex(english)
    sandstone = dialog.template_input.findText("Sandstone")

    assert english >= 0
    assert sandstone >= 0
    assert dialog.template_input.currentIndex() == sandstone
    assert dialog.description_input.text().startswith("Sandstone [X%]")
    assert "quartz-micaceous" in dialog.description_input.text()
    dialog.close()


def test_lithology_dialog_suggests_matching_template_for_lithotype(qapp) -> None:
    session = ProjectSession()
    session.project.wells["well"] = Well("well", "Well")
    session.current_well_id = "well"
    dialog = LithologyDialog(LithologyController(session), language=AppLanguage.KK)

    sandstone = dialog.lithotype_input.findData("sandstone")
    dialog.lithotype_input.setCurrentIndex(sandstone)

    assert dialog.template_language_input.currentData() == AppLanguage.KK.value
    assert dialog.template_input.currentText() == "Құмтастар"
    assert dialog.description_input.text().startswith("Құмтастар [X%]")
    dialog.close()


def test_lithology_dialog_uses_english_catalog_and_labels(qapp) -> None:
    session = ProjectSession()
    session.project.wells["well"] = Well("well", "Well")
    session.current_well_id = "well"
    dialog = LithologyDialog(
        LithologyController(session),
        language=AppLanguage.EN,
    )
    table = dialog.findChild(QTableWidget, "lithology-intervals-table")
    buttons = dialog.findChild(QDialogButtonBox)

    assert table is not None
    assert buttons is not None
    assert dialog.windowTitle() == "Lithology intervals"
    assert table.horizontalHeaderItem(0).text() == "Top"
    assert table.horizontalHeaderItem(3).text() == "Description"
    sandstone = dialog.lithotype_input.findData("sandstone")
    assert dialog.lithotype_input.itemText(sandstone) == "Sandstone (sandstone)"
    assert dialog.findChild(QPushButton, "lithology-add-button").text() == "Add"
    assert buttons.button(QDialogButtonBox.StandardButton.Close).text() == "Close"
    dialog.close()


def test_lithology_dialog_uses_kazakh_catalog_names(qapp) -> None:
    session = ProjectSession()
    session.project.wells["well"] = Well("well", "Well")
    session.current_well_id = "well"
    dialog = LithologyDialog(LithologyController(session), language=AppLanguage.KK)

    sandstone = dialog.lithotype_input.findData("sandstone")

    assert dialog.lithotype_input.itemText(sandstone) == "Құмтас (sandstone)"
    dialog.close()


def test_factory_template_populates_and_saves_all_lithology_languages(qapp) -> None:
    session = ProjectSession()
    session.project.wells["well"] = Well("well", "Well")
    session.current_well_id = "well"
    dialog = LithologyDialog(LithologyController(session), language=AppLanguage.RU)
    dialog.top_input.setValue(100.0)
    dialog.bottom_input.setValue(101.0)

    sandstone = dialog.lithotype_input.findData("sandstone")
    dialog.lithotype_input.setCurrentIndex(sandstone)
    dialog._add()

    interval = session.current_well.lithology[0]
    assert set(interval.description_i18n) == {"ru", "kk", "en"}
    assert interval.description_i18n["ru"].startswith("Песчаники [X%]")
    assert interval.description_i18n["kk"].startswith("Құмтастар [X%]")
    assert interval.description_i18n["en"].startswith("Sandstone [X%]")
    assert interval.description == interval.description_i18n["ru"]
    dialog.close()


def test_lithology_language_tabs_keep_independent_drafts(qapp) -> None:
    session = ProjectSession()
    session.project.wells["well"] = Well("well", "Well")
    session.current_well_id = "well"
    dialog = LithologyDialog(LithologyController(session), language=AppLanguage.RU)

    drafts = {"ru": "Аргиллит", "kk": "Сазтас", "en": "Argillite"}
    for language_code, text in drafts.items():
        dialog.description_inputs[language_code].setText(text)
        dialog._description_dirty_languages.add(language_code)
    dialog.description_language_tabs.setCurrentIndex(2)
    dialog.description_language_tabs.setCurrentIndex(0)

    assert dialog._description_values() == drafts
    dialog.close()


def test_editing_legacy_lithology_without_ru_does_not_promote_fallback(qapp) -> None:
    interval = LithologyInterval(
        "interval",
        100.0,
        101.0,
        "sandstone",
        description="Legacy authored description",
        description_i18n={"und": "Unclassified authored description"},
    )
    well = Well("well", "Well", lithology=[interval])
    session = ProjectSession()
    session.project.wells[well.well_id] = well
    session.current_well_id = well.well_id
    dialog = LithologyDialog(LithologyController(session), language=AppLanguage.RU)
    dialog.table.selectRow(0)

    dialog.bottom_input.setValue(102.0)
    dialog._update()

    assert interval.description == "Legacy authored description"
    assert interval.description_i18n == {"und": "Unclassified authored description"}
    dialog.close()
