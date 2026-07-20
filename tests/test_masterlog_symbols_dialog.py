from hashlib import sha256

import numpy as np
from PySide6.QtWidgets import QTableWidget

from geoworkbench.domain.models import (
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    MasterlogColumnTemplate,
    MasterlogTemplate,
)
from geoworkbench.printing.image_assets import ImageAsset
from geoworkbench.project.masterlog_symbol_controller import MasterlogSymbolController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.masterlog_symbols_dialog import MasterlogSymbolsDialog


def make_controller() -> MasterlogSymbolController:
    dataset = Dataset("dataset", "Log", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 200.0]))
    session = ProjectSession()
    session.add_dataset(dataset, "Well")
    dataset.upsert_curve("TG", np.array([1.0, 100.0]))
    dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.DATETIME,
            IndexRole.TIME,
            "UTC",
            np.array(["2026-07-15T05:00:00", "2026-07-15T05:00:10"], dtype="datetime64[ns]"),
            timezone="UTC",
        )
    )
    session.project.masterlog_templates["standard"] = MasterlogTemplate(
        "standard",
        "Standard",
        columns=[MasterlogColumnTemplate("gas", "Gas", "curves", 40.0, ["TG"])],
    )
    payload = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
    digest = sha256(payload).hexdigest()
    asset = ImageAsset(f"sha256:{digest}", "show.svg", "image/svg+xml", payload)
    session.image_assets[asset.asset_id] = asset
    return MasterlogSymbolController(session)


def test_masterlog_symbols_dialog_adds_and_undoes_symbol(qapp) -> None:
    controller = make_controller()
    dialog = MasterlogSymbolsDialog(controller, "standard", language=AppLanguage.EN)
    dialog.depth_input.setValue(150.0)
    dialog.label_input.setText("Gas show")

    dialog._add()

    table = dialog.findChild(QTableWidget, "masterlog-symbols-table")
    assert table is not None
    assert table.rowCount() == 1
    assert table.item(0, 4).text() == "Gas show"
    assert dialog.undo_button.isEnabled()
    dialog._undo()
    assert table.rowCount() == 0
    dialog._redo()
    assert table.rowCount() == 1
    dialog.close()


def test_masterlog_symbols_dialog_adds_interval(qapp) -> None:
    controller = make_controller()
    dialog = MasterlogSymbolsDialog(controller, "standard", language=AppLanguage.EN)
    dialog.anchor_input.setCurrentIndex(dialog.anchor_input.findData("interval"))
    dialog.depth_input.setValue(120.0)
    dialog.bottom_depth_input.setValue(180.0)

    dialog._add()

    symbol = controller.available("standard")[0]
    assert symbol.anchor_type == "interval"
    assert symbol.bottom_depth == 180.0
    assert dialog.table.item(0, 0).text() == "120–180"
    assert dialog.height_input.isEnabled() is False
    dialog.close()


def test_masterlog_symbols_dialog_adds_parameter_anchor(qapp) -> None:
    controller = make_controller()
    dialog = MasterlogSymbolsDialog(controller, "standard", language=AppLanguage.EN)
    dialog.anchor_input.setCurrentIndex(dialog.anchor_input.findData("parameter"))
    dialog.depth_input.setValue(190.0)

    assert dialog.parameter_input.currentData() == "TG"
    dialog._add()

    symbol = controller.available("standard")[0]
    assert symbol.anchor_type == "parameter"
    assert symbol.parameter_mnemonic == "TG"
    assert dialog.parameter_input.isVisibleTo(dialog) is True
    dialog.close()


def test_masterlog_symbols_dialog_adds_time_anchor(qapp) -> None:
    controller = make_controller()
    dialog = MasterlogSymbolsDialog(controller, "standard", language=AppLanguage.EN)
    dialog.anchor_input.setCurrentIndex(dialog.anchor_input.findData("time"))
    dialog.time_input.setText("2026-07-15T10:00:09+05:00")

    dialog._add()

    symbol = controller.available("standard")[0]
    assert symbol.anchor_type == "time"
    assert symbol.top_depth == 200.0
    assert dialog.time_input.isVisibleTo(dialog) is True
    dialog.close()
