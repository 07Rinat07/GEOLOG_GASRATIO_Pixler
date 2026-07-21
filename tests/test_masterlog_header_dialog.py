import base64
from hashlib import sha256

from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.image_asset_rendering import image_asset_pixmap
from geoworkbench.printing.image_assets import ImageAsset
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.masterlog_header_dialog import HeaderElementDialog, MasterlogHeaderDialog


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"><rect width="20" height="10" fill="#f00"/></svg>'


def make_image_asset() -> ImageAsset:
    digest = sha256(PNG).hexdigest()
    return ImageAsset(f"sha256:{digest}", "logo.png", "image/png", PNG)


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

    dialog = MasterlogHeaderDialog(controller, template.template_id, language=AppLanguage.EN)

    assert dialog.windowTitle() == "Masterlog header elements"
    assert dialog.list.item(0).text() == "Title\ntext · 5,6 · 80×10 mm"
    assert dialog.preview.objectName() == "masterlog-header-preview"
    assert dialog.preset_button.text() == "Apply header preset..."
    assert len(dialog.preview_scene.items()) >= 3
    assert any(getattr(item, "zValue", lambda: 0.0)() == -10 for item in dialog.preview_scene.items())
    assert dialog.preview_scene.sceneRect().width() == 214.0
    dialog.close()


def test_header_element_dialog_builds_typed_properties(qapp) -> None:
    dialog = HeaderElementDialog(language=AppLanguage.EN)
    dialog.type_input.setCurrentText("text")
    dialog.text_input.setText("Daily masterlog")
    dialog.text_color_input.setText("#123456")
    dialog.font_size_input.setValue(4.5)
    assert dialog.values()[-1] == {
        "text": "Daily masterlog",
        "color": "#123456",
        "font_size_mm": 4.5,
        "bold": False,
        "alignment": "left",
        "frame": False,
        "text_orientation": "horizontal",
        "text_position": "center",
    }

    dialog.type_input.setCurrentText("field")
    dialog.field_input.setCurrentIndex(dialog.field_input.findData("well.name"))
    assert dialog.values()[-1] == {
        "field": "well.name",
        "color": "#123456",
        "font_size_mm": 4.5,
        "bold": False,
        "alignment": "left",
        "frame": False,
        "text_orientation": "horizontal",
        "text_position": "center",
    }
    assert dialog.windowTitle() == "Header element properties"
    dialog.close()


def test_header_element_dialog_builds_rotated_and_anchored_text_properties(qapp) -> None:
    dialog = HeaderElementDialog(language=AppLanguage.RU)
    dialog.type_input.setCurrentText("text")
    dialog.text_input.setText("Стратиграфия")
    dialog.text_orientation_input.setCurrentIndex(
        dialog.text_orientation_input.findData("vertical_bottom_to_top")
    )
    dialog.text_position_input.setCurrentIndex(dialog.text_position_input.findData("bottom"))

    properties = dialog.values()[-1]

    assert properties["text_orientation"] == "vertical_bottom_to_top"
    assert properties["text_position"] == "bottom"
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
    assert dialog.values()[-1] == {
        "field": "legacy.custom",
        "color": "#0f172a",
        "font_size_mm": 3.5,
        "bold": False,
        "alignment": "left",
        "frame": False,
        "text_orientation": "horizontal",
        "text_position": "center",
    }
    dialog.close()


def test_header_element_dialog_builds_line_properties(qapp) -> None:
    dialog = HeaderElementDialog(language=AppLanguage.EN)
    dialog.type_input.setCurrentText("line")
    dialog.line_color_input.setText("#ff0000")
    dialog.line_width_input.setValue(1.25)

    assert dialog.values()[-1] == {"color": "#ff0000", "width": 1.25}
    dialog.close()


def test_header_element_dialog_builds_lithology_legend_properties(qapp) -> None:
    dialog = HeaderElementDialog(language=AppLanguage.EN)
    dialog.type_input.setCurrentText("lithology_legend")
    dialog.legend_scope_input.setCurrentIndex(dialog.legend_scope_input.findData("all"))
    dialog.legend_columns_input.setValue(6)
    dialog.legend_code_input.setChecked(False)
    dialog.text_color_input.setText("#223344")
    dialog.font_size_input.setValue(2.8)

    assert dialog.values()[-1] == {
        "scope": "all",
        "columns": 6,
        "show_code": False,
        "selected_lithotype_ids": [],
        "color": "#223344",
        "font_size_mm": 2.8,
        "bold": False,
        "alignment": "left",
        "frame": False,
    }
    assert dialog.legend_scope_input.currentText() == "Full catalog"
    dialog.close()


def test_header_element_dialog_selects_project_png_asset(qapp) -> None:
    asset = make_image_asset()
    dialog = HeaderElementDialog(image_assets={asset.asset_id: asset})
    dialog.type_input.setCurrentText("image")

    assert dialog.image_input.currentText() == "logo.png"
    assert dialog.values()[-1] == {
        "asset_ref": asset.asset_id,
        "mode": "fit",
        "rotation": 0.0,
        "opacity": 1.0,
    }
    dialog.close()


def test_header_element_dialog_stages_png_import_until_apply(qapp, tmp_path, monkeypatch) -> None:
    source = tmp_path / "new-logo.png"
    source.write_bytes(PNG)
    dialog = HeaderElementDialog()
    monkeypatch.setattr(
        "geoworkbench.ui.masterlog_header_dialog.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(source), "PNG (*.png)"),
    )

    dialog._import_image()

    assert len(dialog.imported_assets) == 1
    assert dialog.image_input.currentText() == "new-logo.png"
    dialog.close()


def test_header_element_dialog_reuses_duplicate_project_png(qapp, tmp_path, monkeypatch) -> None:
    source = tmp_path / "duplicate-name.png"
    source.write_bytes(PNG)
    asset = make_image_asset()
    dialog = HeaderElementDialog(image_assets={asset.asset_id: asset})
    monkeypatch.setattr(
        "geoworkbench.ui.masterlog_header_dialog.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(source), "PNG (*.png)"),
    )

    dialog._import_image()

    assert dialog.imported_assets == {}
    assert dialog.image_input.currentText() == "logo.png"
    assert dialog.image_input.currentData() == asset.asset_id
    dialog.close()


def test_header_element_dialog_imports_safe_svg(qapp, tmp_path, monkeypatch) -> None:
    source = tmp_path / "vector-logo.svg"
    source.write_bytes(SVG)
    dialog = HeaderElementDialog()
    monkeypatch.setattr(
        "geoworkbench.ui.masterlog_header_dialog.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(source), "Images (*.png *.svg)"),
    )

    dialog._import_image()

    asset = next(iter(dialog.imported_assets.values()))
    assert asset.media_type == "image/svg+xml"
    assert not image_asset_pixmap(asset).isNull()
    assert dialog.image_input.currentText() == "vector-logo.svg"
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
    line = next(
        item
        for item in dialog.preview_scene.items()
        if item.__class__.__name__ == "_MovableHeaderLine"
    )

    assert line.pen().color().name() == "#334155"
    assert line.pen().widthF() == 0.6
    scene_end = line.mapToScene(line.line().p2())
    assert scene_end.x() == 85.0
    assert scene_end.y() == 16.0
    dialog.close()


def test_header_preview_applies_text_style_with_safe_fallback(qapp) -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")
    element = controller.add_header_element(
        template.template_id,
        element_type="text",
        x_mm=0,
        y_mm=0,
        width_mm=30,
        height_mm=10,
        properties={"text": "Title", "color": "invalid", "font_size_mm": 1000},
    )
    dialog = MasterlogHeaderDialog(controller, template.template_id)

    color, size = dialog._text_style(element)

    assert color.name() == "#0f172a"
    assert size == 3.5
    dialog.close()


def test_header_preview_renders_project_png_asset(qapp) -> None:
    asset = make_image_asset()
    session = ProjectSession(image_assets={asset.asset_id: asset})
    controller = MasterlogTemplateController(session)
    template = controller.create("Standard")
    element = controller.add_header_element(
        template.template_id,
        element_type="image",
        x_mm=2,
        y_mm=3,
        width_mm=20,
        height_mm=10,
        properties={"asset_ref": asset.asset_id},
    )
    dialog = MasterlogHeaderDialog(controller, template.template_id)

    assert dialog._add_image_preview(element)
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


def test_header_element_dialog_builds_lba_legend_properties(qapp) -> None:
    dialog = HeaderElementDialog(language=AppLanguage.EN)
    dialog.type_input.setCurrentText("lba_legend")
    dialog.text_color_input.setText("#553311")
    dialog.font_size_input.setValue(2.2)

    assert dialog.values()[-1] == {
        "color": "#553311",
        "font_size_mm": 2.2,
        "bold": False,
        "alignment": "left",
        "frame": False,
    }
    dialog.close()


def test_optional_logo_placeholder_can_remain_empty_and_preserves_metadata(qapp) -> None:
    from geoworkbench.domain.models import MasterlogHeaderElement

    element = MasterlogHeaderElement(
        "logo",
        "image",
        5.0,
        5.0,
        40.0,
        15.0,
        {
            "optional": True,
            "logo_role": "customer",
            "placeholder_text_ru": "Загрузить логотип заказчика",
            "frame": True,
            "background": "#f8fafc",
            "mode": "fit",
        },
    )
    dialog = HeaderElementDialog(element=element, language=AppLanguage.RU)

    properties = dialog.values()[-1]

    assert properties["optional"] is True
    assert properties["logo_role"] == "customer"
    assert properties["placeholder_text_ru"] == "Загрузить логотип заказчика"
    assert "asset_ref" not in properties
    dialog.close()
