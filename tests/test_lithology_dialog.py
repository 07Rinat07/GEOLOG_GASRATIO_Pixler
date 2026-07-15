import numpy as np
from PySide6.QtWidgets import QDialogButtonBox, QPushButton, QTableWidget

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Well
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

    dialog.template_input.setCurrentIndex(1)

    assert dialog.description_input.text() == "Песчаник серый, мелкозернистый"
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
