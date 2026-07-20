from hashlib import sha256

from geoworkbench.printing.image_assets import ImageAsset
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.masterlog_assets_dialog import MasterlogAssetsDialog


def test_masterlog_assets_dialog_lists_renames_and_removes_unused(qapp, monkeypatch) -> None:
    payload = b"\x89PNG\r\n\x1a\nasset"
    digest = sha256(payload).hexdigest()
    asset = ImageAsset(f"sha256:{digest}", "logo.png", "image/png", payload)
    session = ProjectSession(image_assets={asset.asset_id: asset})
    controller = MasterlogTemplateController(session)
    dialog = MasterlogAssetsDialog(controller, language=AppLanguage.EN)

    assert dialog.windowTitle() == "Masterlog images"
    assert dialog.list.item(0).text() == "logo.png — 13 bytes — unused"

    dialog.list.setCurrentRow(0)
    monkeypatch.setattr(
        "geoworkbench.ui.masterlog_assets_dialog.QInputDialog.getText",
        lambda *args, **kwargs: ("Operator logo", True),
    )
    dialog._rename()

    assert dialog.list.item(0).text() == "Operator logo — 13 bytes — unused"

    dialog.list.setCurrentRow(0)
    dialog._delete()

    assert dialog.list.count() == 0
    assert session.image_assets == {}
    dialog.close()


def test_masterlog_assets_dialog_installs_builtin_symbol_once(qapp) -> None:
    session = ProjectSession()
    controller = MasterlogTemplateController(session)
    dialog = MasterlogAssetsDialog(controller, language=AppLanguage.EN)

    dialog.symbol_input.setCurrentIndex(0)
    dialog._add_symbol()
    installed = next(iter(session.image_assets.values()))

    assert installed.media_type == "image/svg+xml"
    assert installed.original_name == "Gas show.svg"
    assert not dialog.list.item(0).icon().isNull()
    assert session.dirty

    session.dirty = False
    dialog._add_symbol()
    assert len(session.image_assets) == 1
    assert not session.dirty
    dialog.close()
