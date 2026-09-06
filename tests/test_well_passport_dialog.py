import base64
from copy import deepcopy
from hashlib import sha256

import pytest
from PySide6.QtWidgets import QDialog, QTextEdit

from geoworkbench.domain.models import MasterlogTemplate, Well
from geoworkbench.domain.well_passport import WellPassport
from geoworkbench.printing.image_assets import ImageAsset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.well_passport_dialog import WellPassportDialog


def make_session() -> ProjectSession:
    session = ProjectSession()
    well = Well("well-1", "Example")
    session.project.wells[well.well_id] = well
    session.current_well_id = well.well_id
    return session


def add_legacy_header(session: ProjectSession, name: str, fields: dict[str, str]) -> None:
    session.project.masterlog_templates[name] = MasterlogTemplate(
        name, name, properties={"header_fields": fields}
    )


def set_text(editor, text: str) -> None:
    if isinstance(editor, QTextEdit):
        editor.setPlainText(text)
    else:
        editor.setText(text)


def test_passport_dialog_reject_preserves_everything(qapp) -> None:
    session = make_session()
    session.current_well.passport = WellPassport(
        values={"header.actual_depth": 100.0},
        texts_i18n={"header.notes": {"ru": "Примечание", "und": "Legacy note"}},
    )
    before = deepcopy(session.project)
    assets = dict(session.image_assets)
    dialog = WellPassportDialog(session)
    dialog.inputs["header.actual_depth"].setText("200")
    set_text(dialog.localized_inputs["en"]["header.notes"], "New note")
    dialog.logo_inputs["customer"].setCurrentIndex(1)

    dialog.reject()

    assert session.project == before
    assert session.image_assets == assets
    assert not session.dirty


@pytest.mark.parametrize(
    ("language", "title"),
    [
        (AppLanguage.RU, "Паспорт скважины"),
        (AppLanguage.KK, "Ұңғыма паспорты"),
        (AppLanguage.EN, "Well passport"),
    ],
)
def test_passport_dialog_localized_ui(qapp, language, title) -> None:
    dialog = WellPassportDialog(make_session(), language=language)
    assert dialog.windowTitle() == title
    assert [dialog.tabs.tabText(index) for index in range(1, 4)] == [
        "Русский",
        "Қазақша",
        "English",
    ]
    assert "header.interval" not in dialog.inputs
    assert "header.interval_start" not in dialog.inputs
    assert "header.scale" not in dialog.inputs


def test_passport_dialog_save_shared_and_three_languages(qapp) -> None:
    session = make_session()
    other = Well("well-2", "Other well", passport=WellPassport(values={"header.actual_depth": 9.0}))
    session.project.wells[other.well_id] = other
    untouched = deepcopy(other)
    dialog = WellPassportDialog(session, language=AppLanguage.KK)
    dialog.inputs["header.actual_depth"].setText("0")
    dialog.inputs["header.project_depth"].setText("5500,25")
    dialog.inputs["header.latitude"].setText("46.4683")
    dialog.inputs["header.well_number"].setText("CG-8")
    dialog.inputs["header.start_date"].setText("2026-09-05")
    translations = {"ru": "Песчаник", "kk": "Құмтас", "en": "Sandstone"}
    for language, value in translations.items():
        set_text(dialog.localized_inputs[language]["header.notes"], value)

    dialog.accept()

    assert dialog.result() == QDialog.DialogCode.Accepted
    passport = session.current_well.passport
    assert passport.values["header.actual_depth"] == 0.0
    assert passport.values["header.project_depth"] == 5500.25
    assert passport.values["header.start_date"] == "2026-09-05"
    assert passport.values["header.well_number"] == "CG-8"
    assert passport.texts_i18n["header.notes"] == translations
    assert "header.country" not in passport.texts_i18n
    assert session.dirty
    assert other == untouched


def test_passport_dialog_legacy_conflicts_need_explicit_choice(qapp) -> None:
    session = make_session()
    add_legacy_header(session, "Portrait", {"header.actual_depth": "1000"})
    add_legacy_header(session, "Landscape", {"header.actual_depth": "1200"})
    before = deepcopy(session.project.masterlog_templates)
    dialog = WellPassportDialog(session)
    combo = dialog.source_combos["header.actual_depth", ""]

    assert combo.currentIndex() == 0
    assert dialog.inputs["header.actual_depth"].text() == ""
    assert combo.count() == 3
    combo.setCurrentIndex(combo.findData("1200"))
    assert dialog.inputs["header.actual_depth"].text() == "1200"
    assert session.current_well.passport is None
    assert not session.dirty
    dialog.accept()

    assert session.current_well.passport.values["header.actual_depth"] == 1200.0
    assert session.project.masterlog_templates == before


def test_passport_dialog_adopts_text_only_into_explicit_language(qapp) -> None:
    session = make_session()
    add_legacy_header(session, "Portrait", {"header.notes": "Ручная запись"})
    dialog = WellPassportDialog(session, language=AppLanguage.EN)
    dialog.source_combos["header.notes", "ru"].setCurrentIndex(1)
    dialog.accept()

    assert session.current_well.passport.texts_i18n["header.notes"] == {"ru": "Ручная запись"}


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("header.actual_depth", "1000 м"),
        ("header.actual_depth", "nan"),
        ("header.actual_depth", "-1"),
        ("header.latitude", "91"),
        ("header.longitude", "53°35′06.40″E"),
        ("header.start_date", "05.09.2026"),
        ("header.start_date", "2026-02-30"),
    ],
)
def test_passport_dialog_invalid_values_do_not_mutate(qapp, monkeypatch, field_name, value) -> None:
    session = make_session()
    session.current_well.passport = WellPassport(values={"header.actual_depth": 100.0})
    before = deepcopy(session.project)
    messages = []
    monkeypatch.setattr(
        "geoworkbench.ui.well_passport_dialog.QMessageBox.warning",
        lambda _parent, title, text: messages.append((title, text)),
    )
    dialog = WellPassportDialog(session, language=AppLanguage.EN)
    dialog.inputs[field_name].setText(value)

    dialog.accept()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert session.project == before
    assert not session.dirty
    assert len(messages) == 1
    assert messages[0][0] == "Check passport data"
    assert "Changes have not been saved" in messages[0][1]


def test_passport_dialog_reopen_preserves_original_and_float_precision(qapp) -> None:
    session = make_session()
    session.current_well.passport = WellPassport(
        values={"header.actual_depth": 1234.56789012345},
        texts_i18n={"header.notes": {"und": "Original note", "ru": "Заметка"}},
    )
    before = deepcopy(session.current_well.passport)
    dialog = WellPassportDialog(session)
    assert dialog.tabs.count() == 5
    original = dialog.findChild(QTextEdit, "passport-header.notes-und")
    assert original.isReadOnly()
    assert original.toPlainText() == "Original note"
    dialog.accept()

    assert session.current_well.passport == before
    assert not session.dirty


def test_passport_dialog_logo_selection_is_staged_and_explicit(qapp) -> None:
    session = make_session()
    payload = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    asset = ImageAsset(
        f"sha256:{sha256(payload).hexdigest()}", "Customer.png", "image/png", payload
    )
    session.image_assets[asset.asset_id] = asset
    dialog = WellPassportDialog(session)
    customer = dialog.logo_inputs["customer"]
    customer.setCurrentIndex(customer.findData(asset.asset_id))
    dialog.logo_inputs["contractor"].setCurrentIndex(1)
    assert session.current_well.passport is None
    assert not session.dirty
    dialog.accept()

    assert session.current_well.passport.logo_refs == {"customer": asset.asset_id, "contractor": ""}
    assert session.image_assets == {asset.asset_id: asset}


def test_construction_adoption_is_staged_and_keeps_language_versions_separate(qapp) -> None:
    from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController

    session = make_session()
    templates = MasterlogTemplateController(session)
    template = templates.create("A4")
    templates.apply_header_preset(template.template_id, "masterlog_header_a4_portrait")
    before = deepcopy(template)
    session.dirty = False
    dialog = WellPassportDialog(session)
    dialog.source_combos["header.casing_4_diameter", ""].setCurrentIndex(1)
    dialog.source_combos["header.casing_4_depth", ""].setCurrentIndex(1)
    for language in ("ru", "kk", "en"):
        dialog.source_combos["header.casing_4_name", language].setCurrentIndex(1)
    assert dialog.inputs["header.casing_4_diameter"].text() == "177,8"
    assert not session.dirty
    dialog.accept()
    passport = session.current_well.passport
    assert passport.values["header.casing_4_diameter"] == 177.8
    assert passport.values["header.casing_4_depth"] == 5029.78
    assert passport.texts_i18n["header.casing_4_name"] == {
        "ru": "Эксплуатационная кол.",
        "kk": "Пайдалану бағанасы",
        "en": "Production casing",
    }
    assert template == before


def test_main_window_passport_action_saves_current_well(qapp, monkeypatch) -> None:
    from PySide6.QtGui import QAction
    from geoworkbench.ui.main_window import MainWindow

    window = MainWindow(language=AppLanguage.EN)
    well = Well("well-1", "Example")
    window.session.project.wells[well.well_id] = well
    window.session.current_well_id = well.well_id

    def fill_and_accept(dialog):
        dialog.inputs["header.actual_depth"].setText("1234.5")
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(WellPassportDialog, "exec", fill_and_accept)
    actions = [
        action for action in window.findChildren(QAction) if action.text() == "Well passport…"
    ]
    assert len(actions) == 1
    actions[0].trigger()
    assert well.passport.values["header.actual_depth"] == 1234.5
    assert window.session.dirty
    window.close()
