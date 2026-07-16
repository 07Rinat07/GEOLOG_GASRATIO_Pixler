from PySide6.QtWidgets import QDialogButtonBox, QPushButton

from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.lithotype_catalog_dialog import LithotypeCatalogDialog


def test_catalog_dialog_adds_project_lithotype(qapp) -> None:
    session = ProjectSession()
    dialog = LithotypeCatalogDialog(LithotypeCatalogController(session))
    dialog.id_input.setText("oil_sand")
    dialog.code_input.setText("OS")
    dialog.name_ru_input.setText("Нефтяной песок")
    dialog.name_kk_input.setText("Мұнайлы құм")
    dialog.name_en_input.setText("Oil sand")
    dialog.category_input.setText("sedimentary")
    dialog.color_input.setText("#a07840")
    dialog.pattern_input.setCurrentText("dots")

    dialog._add()

    assert session.project.lithotypes["oil_sand"].code == "OS"
    assert session.project.lithotypes["oil_sand"].name_kk == "Мұнайлы құм"
    assert dialog.table.rowCount() > len(session.project.lithotypes)
    dialog.close()


def test_catalog_dialog_updates_pattern_preview(qapp) -> None:
    dialog = LithotypeCatalogDialog(LithotypeCatalogController(ProjectSession()))

    dialog.color_input.setText("#112233")
    dialog.pattern_input.setCurrentText("carbonate")
    qapp.processEvents()

    assert dialog.pattern_preview._color == "#112233"
    assert dialog.pattern_preview._pattern_key == "carbonate"
    dialog.close()


def test_catalog_dialog_localizes_labels_without_using_them_as_state(qapp) -> None:
    dialog = LithotypeCatalogDialog(
        LithotypeCatalogController(ProjectSession()),
        language=AppLanguage.EN,
    )
    buttons = dialog.findChild(QDialogButtonBox)

    assert buttons is not None
    assert dialog.windowTitle() == "Rock and lithotype catalog"
    assert dialog.table.horizontalHeaderItem(0).text() == "Source"
    assert dialog.table.horizontalHeaderItem(8).text() == "Pattern"
    assert dialog.table.item(0, 0).text() == "System"
    dialog.table.setCurrentCell(0, 0)
    qapp.processEvents()
    assert dialog.id_input.isReadOnly() is True
    assert dialog.findChild(QPushButton, "catalog-new-button").text() == "New record"
    assert dialog.findChild(QPushButton, "catalog-add-button").text() == "Add"
    assert buttons.button(QDialogButtonBox.StandardButton.Close).text() == "Close"
    dialog.close()
