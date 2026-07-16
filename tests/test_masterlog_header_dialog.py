from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.masterlog_header_dialog import HeaderElementDialog, MasterlogHeaderDialog


def test_masterlog_header_dialog_lists_elements(qapp) -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")
    controller.add_header_element(
        template.template_id,
        element_type="text",
        x_mm=5,
        y_mm=6,
        width_mm=80,
        height_mm=10,
        properties={"text": "Title"},
    )

    dialog = MasterlogHeaderDialog(
        controller, template.template_id, language=AppLanguage.EN
    )

    assert dialog.windowTitle() == "Masterlog header elements"
    assert dialog.list.item(0).text() == "text | 5,6 | 80×10 mm"
    dialog.close()


def test_header_element_dialog_parses_json_properties(qapp) -> None:
    dialog = HeaderElementDialog()
    dialog.type_input.setCurrentText("field")
    dialog.properties_input.setText('{"field": "well.name"}')

    assert dialog.values()[-1] == {"field": "well.name"}
    dialog.close()
