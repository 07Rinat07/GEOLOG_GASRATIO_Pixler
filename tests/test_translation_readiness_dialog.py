from __future__ import annotations

from copy import deepcopy

import numpy as np
from PySide6.QtWidgets import QMenu

from geoworkbench.domain.models import (
    Dataset,
    DatasetKind,
    DepthDomain,
    LithologyInterval,
)
from geoworkbench.domain.translation_status import TranslationState, TranslationStatus
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.translation_status_controller import TranslationStatusController
from geoworkbench.project.well_translation_readiness_controller import (
    WellTranslationReadinessController,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.main_window import MainWindow
from geoworkbench.ui.translation_readiness_dialog import TranslationReadinessDialog


def _session() -> ProjectSession:
    session = ProjectSession()
    session.add_dataset(
        Dataset(
            "dataset",
            "Well A",
            DatasetKind.GTI,
            DepthDomain.MD,
            np.array([100.0, 200.0]),
        )
    )
    session.dirty = False
    return session


def _finish_deferred_navigation(qapp) -> None:
    for _ in range(4):
        qapp.processEvents()


def _menu(window: MainWindow, key: str) -> QMenu:
    return next(
        menu
        for menu in window.findChildren(QMenu)
        if menu.menuAction().property("i18n_key") == key
    )


def test_dialog_filters_real_readiness_without_mutating_project(qapp) -> None:
    session = _session()
    well = session.current_well
    assert well is not None
    well.lithology.extend(
        [
            LithologyInterval(
                "inside",
                100.0,
                110.0,
                "sandstone",
                description_i18n={"ru": "Песчаник"},
            ),
            LithologyInterval(
                "outside",
                150.0,
                160.0,
                "shale",
                description_i18n={"ru": "Аргиллит"},
            ),
        ]
    )
    well.translation_statuses["lithology/inside/description"] = {
        "kk": TranslationStatus(
            state=TranslationState.DRAFT,
            source_language="ru",
            source_revision=1,
            translation_revision=1,
        )
    }
    well.translation_statuses["lithology/outside/description"] = {
        "kk": TranslationStatus(
            state=TranslationState.REVIEWED,
            source_language="ru",
            source_revision=1,
            translation_revision=1,
        )
    }

    statuses_before = deepcopy(well.translation_statuses)
    dirty_before = session.dirty

    dialog = TranslationReadinessDialog(
        WellTranslationReadinessController(session),
        status_controller=TranslationStatusController(session),
        language=AppLanguage.RU,
    )
    kk_index = dialog.target_language_combo.findData("kk")
    assert kk_index >= 0
    dialog.target_language_combo.setCurrentIndex(kk_index)
    dialog.include_reviewed_checkbox.setChecked(True)
    dialog.refresh()

    summary = dialog.last_summary
    assert summary is not None
    assert summary.total_required == 2
    assert summary.draft_count == 1
    assert summary.reviewed_count == 1
    assert dialog.table.rowCount() == 2

    dialog.depth_filter_checkbox.setChecked(True)
    dialog.top_depth_spin.setValue(100.0)
    dialog.bottom_depth_spin.setValue(120.0)
    dialog.refresh()

    summary = dialog.last_summary
    assert summary is not None
    assert summary.total_required == 1
    assert summary.draft_count == 1
    assert summary.reviewed_count == 0
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "Черновик"
    assert dialog.table.item(0, 2).text() == "Литология — описание"
    assert dialog.table.item(0, 2).toolTip() == "lithology/inside/description"
    assert well.translation_statuses == statuses_before
    assert session.dirty is dirty_before

    dialog.set_language(AppLanguage.EN)
    assert dialog.windowTitle() == "Translation readiness"
    assert dialog.table.horizontalHeaderItem(0).text() == "Status"
    assert dialog.table.item(0, 0).text() == "Draft"
    dialog.close()


def test_dialog_rejects_inverted_depth_range_without_querying_invalid_state(qapp) -> None:
    session = _session()
    well = session.current_well
    assert well is not None
    well.lithology.append(
        LithologyInterval(
            "interval",
            100.0,
            110.0,
            "sandstone",
            description_i18n={"ru": "Песчаник"},
        )
    )

    dialog = TranslationReadinessDialog(
        WellTranslationReadinessController(session),
        status_controller=TranslationStatusController(session),
        language=AppLanguage.EN,
    )
    dialog.depth_filter_checkbox.setChecked(True)
    dialog.top_depth_spin.setValue(200.0)
    dialog.bottom_depth_spin.setValue(100.0)
    dialog.refresh()

    assert dialog.last_summary is None
    assert dialog.table.rowCount() == 0
    assert "must be greater" in dialog.message_label.text()
    dialog.close()


def test_navigation_exposes_localized_translation_readiness_action(qapp) -> None:
    window = MainWindow(language=AppLanguage.RU)
    window.show()
    _finish_deferred_navigation(qapp)

    tools_menu = _menu(window, "menu.tools")
    assert window.translation_readiness_action in tools_menu.actions()
    assert window.translation_readiness_action.objectName() == "translationReadinessAction"
    assert window.translation_readiness_action.text() == "Готовность переводов..."

    window.translation_readiness_action.trigger()
    _finish_deferred_navigation(qapp)

    assert window.translation_readiness_dialog.isVisible()
    assert window.translation_readiness_dialog.windowTitle() == "Готовность переводов"

    window.change_language(AppLanguage.KK)
    _finish_deferred_navigation(qapp)
    assert window.translation_readiness_action.text() == "Аудармалардың дайындығы..."
    assert window.translation_readiness_dialog.windowTitle() == "Аудармалардың дайындығы"

    window.change_language(AppLanguage.EN)
    _finish_deferred_navigation(qapp)
    assert window.translation_readiness_action.text() == "Translation readiness..."
    assert window.translation_readiness_dialog.windowTitle() == "Translation readiness"

    window.translation_readiness_dialog.close()
    window.close()


def test_dialog_reviews_selected_current_draft(qapp) -> None:
    session = _session()
    well = session.current_well
    assert well is not None
    field_id = "lithology/interval/description"
    well.lithology.append(
        LithologyInterval(
            "interval",
            100.0,
            110.0,
            "sandstone",
            description_i18n={"ru": "Песчаник", "kk": "Құмтас"},
        )
    )
    well.authored_field_revisions[field_id] = 1
    well.authored_field_source_languages[field_id] = "ru"
    well.translation_statuses[field_id] = {
        "kk": TranslationStatus(
            state=TranslationState.DRAFT,
            source_language="ru",
            source_revision=1,
            translation_revision=1,
        )
    }
    session.dirty = False
    status_controller = TranslationStatusController(session)
    dialog = TranslationReadinessDialog(
        WellTranslationReadinessController(session),
        status_controller=status_controller,
        language=AppLanguage.RU,
    )
    kk_index = dialog.target_language_combo.findData("kk")
    assert kk_index >= 0
    dialog.target_language_combo.setCurrentIndex(kk_index)
    dialog.refresh()

    assert dialog.table.rowCount() == 1
    assert dialog.review_button.isEnabled() is False
    dialog.table.selectRow(0)
    assert dialog.review_button.isEnabled() is True

    dialog.review_button.click()

    reviewed = status_controller.status(field_id, "kk")
    assert reviewed is not None
    assert reviewed.state is TranslationState.REVIEWED
    assert session.dirty is True
    assert dialog.last_summary is not None
    assert dialog.last_summary.reviewed_count == 1
    assert dialog.table.rowCount() == 0
    dialog.close()


def test_dialog_does_not_offer_review_for_stale_translation(qapp) -> None:
    session = _session()
    well = session.current_well
    assert well is not None
    field_id = "lithology/interval/description"
    well.lithology.append(
        LithologyInterval(
            "interval",
            100.0,
            110.0,
            "sandstone",
            description_i18n={"ru": "Песчаник", "en": "Sandstone"},
        )
    )
    well.authored_field_revisions[field_id] = 2
    well.authored_field_source_languages[field_id] = "ru"
    well.translation_statuses[field_id] = {
        "en": TranslationStatus(
            state=TranslationState.DRAFT,
            source_language="ru",
            source_revision=1,
            translation_revision=1,
        )
    }
    dialog = TranslationReadinessDialog(
        WellTranslationReadinessController(session),
        status_controller=TranslationStatusController(session),
        language=AppLanguage.EN,
    )
    en_index = dialog.target_language_combo.findData("en")
    assert en_index >= 0
    dialog.target_language_combo.setCurrentIndex(en_index)
    dialog.refresh()

    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "Stale"
    dialog.table.selectRow(0)
    assert dialog.review_button.isEnabled() is False
    dialog.close()

