from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.session import ProjectSession
from geoworkbench.ui.lithotype_catalog_dialog import LithotypeCatalogDialog


def test_catalog_dialog_adds_project_lithotype(qapp) -> None:
    session = ProjectSession()
    dialog = LithotypeCatalogDialog(LithotypeCatalogController(session))
    dialog.id_input.setText("oil_sand")
    dialog.code_input.setText("OS")
    dialog.name_ru_input.setText("Нефтяной песок")
    dialog.name_en_input.setText("Oil sand")
    dialog.category_input.setText("sedimentary")
    dialog.color_input.setText("#a07840")
    dialog.pattern_input.setText("dots")

    dialog._add()

    assert session.project.lithotypes["oil_sand"].code == "OS"
    assert dialog.table.rowCount() > len(session.project.lithotypes)
    dialog.close()
