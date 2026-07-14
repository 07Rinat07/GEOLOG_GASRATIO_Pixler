from geoworkbench.project.description_template_controller import DescriptionTemplateController
from geoworkbench.project.session import ProjectSession
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
