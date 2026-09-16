from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from geoworkbench.domain.models import LithologyInterval, Well
from geoworkbench.domain.translation_status import TranslationState
from geoworkbench.project.lithology_controller import LithologyController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.lithology_dialog import LithologyDialog


def _session() -> ProjectSession:
    session = ProjectSession()
    session.project.wells["well"] = Well("well", "Well")
    session.current_well_id = "well"
    return session


def test_factory_template_sets_explicit_source_language_and_tracking(qapp) -> None:
    session = _session()
    dialog = LithologyDialog(LithologyController(session), language=AppLanguage.RU)
    dialog.top_input.setValue(100.0)
    dialog.bottom_input.setValue(101.0)

    sandstone = dialog.lithotype_input.findData("sandstone")
    dialog.lithotype_input.setCurrentIndex(sandstone)
    assert dialog.source_language_input.currentData() == "ru"

    dialog._add()

    well = session.current_well
    assert well is not None
    interval = well.lithology[0]
    field_id = f"lithology/{interval.interval_id}/description"
    assert well.authored_field_source_languages[field_id] == "ru"
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.DRAFT
    assert well.translation_statuses[field_id]["en"].state is TranslationState.DRAFT
    dialog.close()


def test_manual_first_edit_selects_that_language_as_source(qapp) -> None:
    session = _session()
    dialog = LithologyDialog(LithologyController(session), language=AppLanguage.RU)
    source_combo = dialog.findChild(QComboBox, "lithology-source-language")
    assert source_combo is not None
    assert source_combo.currentData() is None

    dialog.description_inputs["en"].setText("Sandstone")
    dialog._description_edited("en")

    assert source_combo.currentData() == "en"
    dialog.close()


def test_legacy_interval_load_does_not_infer_source_from_fallback(qapp) -> None:
    interval = LithologyInterval(
        "legacy",
        100.0,
        101.0,
        "sandstone",
        description="Legacy authored description",
        description_i18n={"und": "Unclassified authored description"},
    )
    session = _session()
    well = session.current_well
    assert well is not None
    well.lithology.append(interval)
    dialog = LithologyDialog(LithologyController(session), language=AppLanguage.RU)

    dialog.table.selectRow(0)

    assert dialog.source_language_input.currentData() is None
    assert dialog.description_inputs["ru"].text() == "Legacy authored description"
    assert well.authored_field_source_languages == {}
    dialog.close()


def test_existing_tracked_interval_loads_persisted_source_language(qapp) -> None:
    session = _session()
    controller = LithologyController(session)
    interval = controller.add(
        100.0,
        101.0,
        "sandstone",
        description_i18n={"ru": "Песчаник", "kk": "Құмтас", "en": "Sandstone"},
        source_language="kk",
    )
    dialog = LithologyDialog(controller, language=AppLanguage.RU)

    dialog.table.selectRow(0)

    assert dialog.controller.get(interval.interval_id) is interval
    assert dialog.source_language_input.currentData() == "kk"
    dialog.close()
