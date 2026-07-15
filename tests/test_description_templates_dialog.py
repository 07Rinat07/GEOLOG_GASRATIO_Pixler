from PySide6.QtWidgets import QDialogButtonBox, QPushButton

from geoworkbench.project.description_template_controller import DescriptionTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.description_templates_dialog import DescriptionTemplatesDialog


def test_description_templates_dialog_adds_template(qapp) -> None:
    session = ProjectSession()
    dialog = DescriptionTemplatesDialog(DescriptionTemplateController(session))
    dialog.name_input.setText("Аргиллит")
    dialog.text_input.setPlainText("Аргиллит тёмно-серый, плотный")

    dialog._add()

    assert session.project.description_templates["Аргиллит"].startswith("Аргиллит")
    assert dialog.table.rowCount() == 1
    dialog.close()


def test_description_templates_dialog_uses_selected_language(qapp) -> None:
    dialog = DescriptionTemplatesDialog(
        DescriptionTemplateController(ProjectSession()),
        language=AppLanguage.EN,
    )
    buttons = dialog.findChild(QDialogButtonBox)

    assert buttons is not None
    assert dialog.windowTitle() == "Rock description templates"
    assert dialog.table.horizontalHeaderItem(0).text() == "Name"
    assert dialog.table.horizontalHeaderItem(1).text() == "Text"
    assert dialog.findChild(QPushButton, "template-add-button").text() == "Add"
    assert dialog.findChild(QPushButton, "template-update-button").text() == "Update"
    assert dialog.findChild(QPushButton, "template-remove-button").text() == "Remove"
    assert buttons.button(QDialogButtonBox.StandardButton.Close).text() == "Close"
    dialog.close()
