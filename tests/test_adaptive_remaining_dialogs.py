from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.import_jobs import ImportSourceKind
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.semantic_channels import SemanticChannelDictionary
from geoworkbench.ui.import_review_dialog import ImportReviewDialog
from geoworkbench.ui.masterlog_interval_fill_dialog import CuttingsCompositionDialog
from geoworkbench.ui.masterlog_templates_dialog import MasterlogTemplatesDialog
from geoworkbench.ui.paradox_batch_dialog import ParadoxBatchDialog


def _assert_visible_inside_work_area(dialog, qapp) -> None:
    dialog.show()
    qapp.processEvents()

    screen = dialog.screen()
    assert screen is not None
    assert screen.availableGeometry().contains(dialog.geometry())


def _review_dataset() -> Dataset:
    dataset = Dataset(
        "adaptive-review",
        "Adaptive review",
        DatasetKind.USER,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]),
    )
    semantic = SemanticChannelDictionary().resolve("ROP", unit="m/h")
    dataset.curves = {
        "rop": CurveData(
            CurveMetadata(
                "rop",
                "ROP",
                semantic.canonical_mnemonic,
                "m/h",
                "Rate of penetration",
                dataset.dataset_id,
                semantic=semantic,
            ),
            np.array([5.0, 6.0, 7.0]),
        )
    }
    return dataset


def test_cuttings_composition_actions_remain_visible(qapp) -> None:
    catalog = (
        CatalogLithotype(
            "sandstone",
            "SS",
            "Песчаник",
            "Sandstone",
            "sedimentary",
            "#d6b56c",
            "sandstone",
            False,
            "Құмтас",
        ),
    )
    dialog = CuttingsCompositionDialog(
        100.0,
        101.0,
        catalog,
        language=AppLanguage.RU,
    )

    _assert_visible_inside_work_area(dialog, qapp)
    assert dialog.buttons.isVisible()
    assert dialog.buttons.geometry().bottom() <= dialog.contentsRect().bottom()
    dialog.close()


def test_masterlog_template_library_uses_scrollable_actions(qapp) -> None:
    dialog = MasterlogTemplatesDialog(
        MasterlogTemplateController(ProjectSession()),
        language=AppLanguage.RU,
    )

    _assert_visible_inside_work_area(dialog, qapp)
    assert dialog.actions_scroll.isVisible()
    assert dialog.actions_scroll.horizontalScrollBarPolicy().value >= 0
    dialog.close()


def test_paradox_batch_keeps_primary_actions_visible(qapp, tmp_path: Path) -> None:
    dialog = ParadoxBatchDialog(
        (tmp_path / "source.db",),
        language=AppLanguage.RU,
    )

    _assert_visible_inside_work_area(dialog, qapp)
    assert dialog.start.isVisible()
    assert dialog.close_button.isVisible()
    assert dialog.secondary_actions_scroll.isVisible()
    dialog.close()


def test_import_review_actions_remain_visible(qapp) -> None:
    dialog = ImportReviewDialog(
        _review_dataset(),
        Path("well.las"),
        ImportSourceKind.LAS,
        language=AppLanguage.RU,
    )

    _assert_visible_inside_work_area(dialog, qapp)
    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is dialog.buttons
    assert buttons.isVisible()
    assert buttons.geometry().bottom() <= dialog.contentsRect().bottom()
    dialog.close()
