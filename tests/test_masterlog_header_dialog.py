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
    assert dialog.preview.objectName() == "masterlog-header-preview"
    assert len(dialog.preview_scene.items()) == 3
    assert dialog.preview_scene.sceneRect().width() == 214.0
    dialog.close()


def test_header_element_dialog_builds_typed_properties(qapp) -> None:
    dialog = HeaderElementDialog(language=AppLanguage.EN)
    dialog.type_input.setCurrentText("text")
    dialog.text_input.setText("Daily masterlog")
    assert dialog.values()[-1] == {"text": "Daily masterlog"}

    dialog.type_input.setCurrentText("field")
    dialog.field_input.setCurrentText("well.name")
    assert dialog.values()[-1] == {"field": "well.name"}
    assert dialog.windowTitle() == "Header element properties"
    dialog.close()


def test_header_element_dialog_preserves_unknown_legacy_field(qapp) -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")
    element = controller.add_header_element(
        template.template_id,
        element_type="field",
        x_mm=0,
        y_mm=0,
        width_mm=30,
        height_mm=10,
        properties={"field": "legacy.custom"},
    )

    dialog = HeaderElementDialog(element=element)

    assert dialog.field_input.currentText() == "legacy.custom"
    assert dialog.values()[-1] == {"field": "legacy.custom"}
    dialog.close()


def test_header_element_dialog_builds_line_properties(qapp) -> None:
    dialog = HeaderElementDialog(language=AppLanguage.EN)
    dialog.type_input.setCurrentText("line")
    dialog.line_color_input.setText("#ff0000")
    dialog.line_width_input.setValue(1.25)

    assert dialog.values()[-1] == {"color": "#ff0000", "width": 1.25}
    dialog.close()


def test_header_preview_draws_line_with_safe_style_fallback(qapp) -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")
    controller.add_header_element(
        template.template_id,
        element_type="line",
        x_mm=5,
        y_mm=6,
        width_mm=80,
        height_mm=10,
        properties={"color": "invalid", "width": 1000},
    )

    dialog = MasterlogHeaderDialog(controller, template.template_id)
    line = next(item for item in dialog.preview_scene.items() if hasattr(item, "line"))

    assert line.pen().color().name() == "#334155"
    assert line.pen().widthF() == 0.6
    assert line.line().x2() == 85.0
    assert line.line().y2() == 16.0
    dialog.close()


def test_header_preview_resolves_whitelisted_field_and_marks_unknown(qapp) -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")
    known = controller.add_header_element(
        template.template_id,
        element_type="field",
        x_mm=0,
        y_mm=0,
        width_mm=30,
        height_mm=10,
        properties={"field": "project.name"},
    )
    unknown = controller.add_header_element(
        template.template_id,
        element_type="field",
        x_mm=35,
        y_mm=0,
        width_mm=30,
        height_mm=10,
        properties={"field": "project.secret"},
    )
    dialog = MasterlogHeaderDialog(controller, template.template_id)

    assert dialog._preview_text(known) == "Новый проект"
    assert dialog._preview_text(unknown) == "{project.secret}"
    dialog.close()
