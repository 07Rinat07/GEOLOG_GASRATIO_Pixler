from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QDialogButtonBox, QScrollArea

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.nct_controller import NctCalculationController
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.stratigraphy_catalog_controller import (
    StratigraphyCatalogController,
)
from geoworkbench.project.stratigraphy_controller import StratigraphyController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.nct_dialog import NctCalculationDialog
from geoworkbench.ui.rock_description_dialog import RockDescriptionDialog
from geoworkbench.ui.sample_analysis_dialog import SampleAnalysisDialog
from geoworkbench.ui.stratigraphy_dialog import (
    StratigraphyCatalogDialog,
    StratigraphyDialog,
    StratigraphyIntervalDialog,
)


def _session() -> ProjectSession:
    session = ProjectSession()
    dataset = Dataset(
        "adaptive-geology",
        "Well",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 200.0, 300.0, 400.0]),
    )
    dataset.upsert_curve(
        "DEXPC",
        np.array([1.0, 1.1, 1.2, 1.3]),
        unit="dimensionless",
    )
    session.add_dataset(dataset)
    return session


def _assert_footer_visible(dialog, qapp) -> None:
    dialog.show()
    qapp.processEvents()

    screen = dialog.screen()
    assert screen is not None
    available = screen.availableGeometry()
    geometry = dialog.geometry()
    assert geometry.left() >= available.left()
    assert geometry.top() >= available.top()
    assert geometry.right() <= available.right()
    assert geometry.bottom() <= available.bottom()

    button_boxes = dialog.findChildren(QDialogButtonBox)
    assert button_boxes
    footer = button_boxes[-1]
    assert footer.isVisibleTo(dialog)
    assert dialog.contentsRect().contains(footer.geometry().center())

    dialog.close()


def test_geology_editors_keep_action_footers_inside_work_area(qapp) -> None:
    session = _session()
    stratigraphy_controller = StratigraphyController(session)
    catalog_controller = StratigraphyCatalogController(session)

    dialogs = (
        SampleAnalysisDialog(100.0, 120.0, language=AppLanguage.RU),
        RockDescriptionDialog(100.0, 120.0, language=AppLanguage.RU),
        StratigraphyIntervalDialog(
            100.0,
            120.0,
            language=AppLanguage.RU,
            catalog_controller=catalog_controller,
        ),
        StratigraphyDialog(
            stratigraphy_controller,
            language=AppLanguage.RU,
            catalog_controller=catalog_controller,
        ),
        StratigraphyCatalogDialog(
            catalog_controller,
            language=AppLanguage.RU,
        ),
        NctCalculationDialog(
            NctCalculationController(session),
            100.0,
            400.0,
            language=AppLanguage.RU,
        ),
    )

    for dialog in dialogs:
        _assert_footer_visible(dialog, qapp)


def test_stratigraphy_long_editors_scroll_separately_from_footer(qapp) -> None:
    session = _session()
    controller = StratigraphyController(session)
    catalog_controller = StratigraphyCatalogController(session)

    dialog = StratigraphyDialog(
        controller,
        language=AppLanguage.EN,
        catalog_controller=catalog_controller,
    )
    catalog = StratigraphyCatalogDialog(
        catalog_controller,
        language=AppLanguage.EN,
    )

    editor_scroll = dialog.findChild(QScrollArea, "stratigraphy-editor-scroll")
    assert editor_scroll is not None
    assert editor_scroll.widgetResizable()
    assert dialog.findChildren(QDialogButtonBox)[-1].parentWidget() is dialog

    catalog_scrolls = catalog.findChildren(QScrollArea)
    assert catalog_scrolls
    assert catalog_scrolls[0].widgetResizable()
    assert catalog.findChildren(QDialogButtonBox)[-1].parentWidget() is catalog

    dialog.close()
    catalog.close()
