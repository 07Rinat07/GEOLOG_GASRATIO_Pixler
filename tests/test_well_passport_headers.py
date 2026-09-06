from copy import deepcopy

import numpy as np
import pytest

from geoworkbench.domain.models import (
    Dataset,
    DatasetKind,
    DepthDomain,
    MasterlogHeaderElement,
    MasterlogTemplate,
    Project,
    Well,
)
from geoworkbench.domain.well_passport import WellPassport
from geoworkbench.printing.header_fields import resolve_header_asset_ref, resolve_header_field
from geoworkbench.printing.masterlog_header_forms import masterlog_header_assets
from geoworkbench.printing.masterlog_renderer import _header_text
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.well_passport_controller import WellPassportController
from geoworkbench.services.localization import AppLanguage


def make_session():
    dataset = Dataset("data", "LAS", DatasetKind.GTI, DepthDomain.MD, np.array([1000.0, 1001.0]))
    first = Well("a", "A", datasets={dataset.dataset_id: dataset})
    other = Well("b", "B")
    return ProjectSession(
        project=Project("project", "Project", wells={"a": first, "b": other}),
        current_well_id="a",
        current_dataset_id="data",
    )


def test_passport_adoption_is_explicit_and_preserves_conflicting_legacy_values():
    session = make_session()
    for orientation, depth in (("portrait", "2000"), ("landscape", "2100")):
        session.project.masterlog_templates[orientation] = MasterlogTemplate(
            orientation,
            orientation,
            properties={"header_fields": {"header.actual_depth": depth}},
        )
    before = deepcopy(session.project.masterlog_templates)
    controller = WellPassportController(session)
    candidates = controller.legacy_candidates("header.actual_depth")
    assert [item.value for item in candidates] == ["2000", "2100"]
    assert session.current_well.passport is None
    assert not session.dirty
    controller.save(WellPassport(values={"header.actual_depth": 0.0}))
    for template in session.project.masterlog_templates.values():
        assert resolve_header_field(session, "header.actual_depth", template) == "0"
    assert session.project.masterlog_templates == before
    assert session.project.wells["b"].passport is None
    assert session.current_dataset.depth.tolist() == [1000.0, 1001.0]


@pytest.mark.parametrize(
    "language,value",
    [
        (AppLanguage.RU, "Казахстан"),
        (AppLanguage.KK, "Қазақстан"),
        (AppLanguage.EN, "Kazakhstan"),
    ],
)
@pytest.mark.parametrize("orientation", ["portrait", "landscape"])
def test_both_header_orientations_resolve_current_passport_language(language, value, orientation):
    session = make_session()
    templates = MasterlogTemplateController(session)
    template = templates.create(orientation)
    templates.apply_header_preset(template.template_id, "masterlog_header_a4_" + orientation)
    WellPassportController(session).save(
        WellPassport(
            values={
                "header.actual_depth": 1500.0,
                "header.latitude": 46.4680555555,
                "header.casing_0_depth": 0.0,
                "header.casing_0_diameter": 177.8,
            },
            texts_i18n={
                "header.country": {"ru": "Казахстан", "kk": "Қазақстан", "en": "Kazakhstan"},
                "header.casing_0_name": {"ru": "Колонна", "kk": "Бағана", "en": "Casing"},
            },
        )
    )
    field = next(
        e for e in template.header_elements if e.properties.get("field") == "header.country"
    )
    assert _header_text(field, session, template, language) == value
    assert resolve_header_field(session, "header.latitude", template, language) == "46.4680555555"
    assert resolve_header_field(session, "header.actual_depth", template, language) == "1500"
    template.properties["header_fields"].update(
        {"header.interval_start": "1000", "header.interval_end": "1001"}
    )
    assert resolve_header_field(session, "header.interval_end", template) == "1001"
    assert resolve_header_field(session, "header.actual_depth", template) == "1500"
    for element in template.header_elements:
        if element.element_id == "casing_0_depth":
            assert _header_text(element, session, template, language) == (
                "0 m" if language is AppLanguage.EN else "0 м"
            )
        if element.element_id == "casing_0_name":
            assert (
                _header_text(element, session, template, language)
                == {"ru": "Колонна", "kk": "Бағана", "en": "Casing"}[language.value]
            )
        if element.element_id == "casing_1_depth":
            assert _header_text(element, session, template, language) == ""


def test_explicit_no_logo_does_not_print_missing_image_placeholder(qapp, monkeypatch):
    from PySide6.QtGui import QImage, QPainter
    from geoworkbench.printing.masterlog_renderer import _paint_header_element

    session = make_session()
    WellPassportController(session).save(WellPassport(logo_refs={"contractor": ""}))
    element = MasterlogHeaderElement("logo", "image", 0, 0, 10, 5, {"logo_role": "contractor"})
    calls = []
    monkeypatch.setattr(
        "geoworkbench.printing.masterlog_renderer._paint_image_placeholder",
        lambda *args: calls.append(args),
    )
    image = QImage(100, 100, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        _paint_header_element(
            painter, element, session, MasterlogTemplate("t", "T"), None, AppLanguage.EN, {}
        )
    finally:
        painter.end()
    assert not calls


def test_language_revision_only_changes_for_edited_passport_language():
    session = make_session()
    controller = WellPassportController(session)
    controller.save(WellPassport(texts_i18n={"header.notes": {"ru": "Исходный", "en": "Original"}}))
    before = dict(session.current_well.language_revisions)
    draft = controller.draft()
    draft.texts_i18n["header.notes"]["en"] = "Edited"
    controller.save(draft)
    assert session.current_well.language_revisions == {**before, "en": before["en"] + 1}


def test_decimal_point_is_visible_on_scaled_passport_header(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter
    from geoworkbench.printing.masterlog_renderer import _paint_header_element
    from geoworkbench.printing.unicode_support import configure_application_unicode_fonts

    configure_application_unicode_fonts(qapp)
    session = make_session()
    WellPassportController(session).save(WellPassport(values={"header.rig": "."}))
    element = MasterlogHeaderElement(
        "rig", "field", 0, 0, 20, 10, {"field": "header.rig", "font_size_mm": 1.8}
    )
    image = QImage(240, 120, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.scale(12, 12)
    try:
        _paint_header_element(
            painter, element, session, MasterlogTemplate("t", "T"), None, AppLanguage.EN, {}
        )
    finally:
        painter.end()
    pixels = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(120, 240, 4)
    assert np.any(pixels[:, :, :3] < 128), "The decimal-point glyph disappeared during scaling"


def test_legacy_header_package_keeps_text_and_binds_construction(tmp_path):
    import json
    from dataclasses import asdict
    from geoworkbench.printing.masterlog_package import load_masterlog_package

    template = MasterlogTemplate(
        "legacy",
        "Legacy",
        header_elements=[
            MasterlogHeaderElement(
                "casing_0_depth", "text", 0, 0, 20, 5, {"text": "123 м", "text_en": "123 m"}
            ),
        ],
    )
    target = tmp_path / "legacy-header.json"
    target.write_text(
        json.dumps({"package_version": 2, "template": asdict(template), "image_assets": {}}),
        encoding="utf-8",
    )
    restored = load_masterlog_package(target).template
    element = restored.header_elements[0]
    session = make_session()
    assert _header_text(element, session, restored, AppLanguage.EN) == "123 m"
    WellPassportController(session).save(WellPassport(values={"header.casing_0_depth": 456.75}))
    assert _header_text(element, session, restored, AppLanguage.EN) == "456.75 m"
    assert element.properties["text"] == "123 м"
    assert element.element_id == "casing_0_depth"


def test_active_passport_empty_fields_do_not_resurrect_las_or_template_values():
    session = make_session()
    template = MasterlogTemplate(
        "t", "T", properties={"header_fields": {"header.actual_depth": "2500"}}
    )
    session.current_dataset.headers["TD"] = "2400"
    controller = WellPassportController(session)
    controller.save(WellPassport())
    assert resolve_header_field(session, "header.actual_depth", template) == ""
    assert resolve_header_field(session, "header.well_number", template) == ""
    element = MasterlogHeaderElement("e", "field", 0, 0, 10, 5, {"field": "header.actual_depth"})
    assert _header_text(element, session, template) == ""


def test_passport_save_is_atomic_noop_safe_and_guards_changed_selection():
    session = make_session()
    controller = WellPassportController(session)
    draft = WellPassport(values={"header.actual_depth": 2000.0})
    controller.save(draft)
    revision = session.current_well.content_revision
    session.dirty = False
    controller.save(draft)
    assert not session.dirty
    assert session.current_well.content_revision == revision
    draft.values["header.actual_depth"] = -1.0
    with pytest.raises(ValueError):
        controller.save(draft)
    assert session.current_well.passport.values["header.actual_depth"] == 2000.0
    assert not session.dirty
    session.current_well_id = "b"
    with pytest.raises(ValueError):
        controller.save(WellPassport())
    assert session.current_well.passport is None


def test_passport_logos_override_roles_without_rewriting_template_assets():
    session = make_session()
    asset = masterlog_header_assets()["bpservices"]
    session.image_assets[asset.asset_id] = asset
    element = MasterlogHeaderElement(
        "image", "image", 0, 0, 10, 5, {"logo_role": "customer", "asset_ref": "original"}
    )
    controller = WellPassportController(session)
    controller.save(WellPassport(logo_refs={"customer": asset.asset_id, "contractor": ""}))
    assert resolve_header_asset_ref(session, element) == asset.asset_id
    assert element.properties["asset_ref"] == "original"
    element.properties["logo_role"] = "contractor"
    assert resolve_header_asset_ref(session, element) == ""
    with pytest.raises(ValueError):
        MasterlogTemplateController(session).remove_image_asset(asset.asset_id)
    element.properties["logo_role"] = ["malformed"]
    assert resolve_header_asset_ref(session, element) == "original"


def test_header_editor_uses_same_values_and_keeps_layout_fields_separate(qapp):
    from geoworkbench.ui.masterlog_header_dialog import HeaderDataDialog, MasterlogHeaderDialog

    session = make_session()
    controller = MasterlogTemplateController(session)
    template = controller.create("Portrait")
    controller.apply_header_preset(template.template_id, "masterlog_header_a4_portrait")
    WellPassportController(session).save(
        WellPassport(texts_i18n={"header.country": {"en": "Kazakhstan"}})
    )
    editor = MasterlogHeaderDialog(controller, template.template_id, language=AppLanguage.EN)
    field = next(
        e for e in template.header_elements if e.properties.get("field") == "header.country"
    )
    assert editor._preview_text(field) == "Kazakhstan"
    assert editor.passport_button.isEnabled()
    layout = HeaderDataDialog(controller, template.template_id)
    assert "header.actual_depth" not in layout.inputs
    assert "header.interval_start" in layout.inputs
    assert "header.scale" in layout.inputs
    layout.close()
    editor.close()
