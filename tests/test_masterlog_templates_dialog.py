from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.masterlog_templates_dialog import MasterlogTemplatesDialog


def test_masterlog_templates_dialog_lists_name_and_version(qapp) -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")
    controller.rename(template.template_id, "Standard 2")

    dialog = MasterlogTemplatesDialog(controller, language=AppLanguage.EN)

    assert dialog.windowTitle() == "Masterlog templates"
    assert dialog.list.count() == 1
    assert dialog.list.item(0).text() == "Standard 2 — version 2"
    assert dialog.create_button.text() == "Create"
    assert dialog.assets_button.text() == "Images..."
    assert dialog.preview_button.text() == "Preview..."
    assert dialog.export_button.text() == "Export PDF..."
    dialog.close()
