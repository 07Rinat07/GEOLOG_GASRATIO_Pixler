from hashlib import sha256

import numpy as np
from PySide6.QtWidgets import QTableWidget

from geoworkbench.domain.models import (
    Dataset,
    DatasetKind,
    DepthDomain,
    MasterlogColumnTemplate,
    MasterlogTemplate,
)
from geoworkbench.printing.image_assets import ImageAsset
from geoworkbench.project.masterlog_symbol_controller import MasterlogSymbolController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.masterlog_symbols_dialog import MasterlogSymbolsDialog


def make_controller() -> MasterlogSymbolController:
    dataset = Dataset(
        "dataset", "Log", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 200.0])
    )
    session = ProjectSession()
    session.add_dataset(dataset, "Well")
    session.project.masterlog_templates["standard"] = MasterlogTemplate(
        "standard",
        "Standard",
        columns=[MasterlogColumnTemplate("gas", "Gas", "curves", 40.0)],
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
    assert table.item(0, 3).text() == "Gas show"
    assert dialog.undo_button.isEnabled()
    dialog._undo()
    assert table.rowCount() == 0
    dialog._redo()
    assert table.rowCount() == 1
    dialog.close()
