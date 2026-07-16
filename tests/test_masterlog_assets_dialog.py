from hashlib import sha256

from geoworkbench.printing.image_assets import ImageAsset
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.masterlog_assets_dialog import MasterlogAssetsDialog


def test_masterlog_assets_dialog_lists_usage_and_removes_unused(qapp) -> None:
    payload = b"\x89PNG\r\n\x1a\nasset"
    digest = sha256(payload).hexdigest()
    asset = ImageAsset(f"sha256:{digest}", "logo.png", "image/png", payload)
    session = ProjectSession(image_assets={asset.asset_id: asset})
    controller = MasterlogTemplateController(session)
    dialog = MasterlogAssetsDialog(controller, language=AppLanguage.EN)

    assert dialog.windowTitle() == "Masterlog images"
    assert dialog.list.item(0).text() == "logo.png — 13 bytes — unused"

    dialog.list.setCurrentRow(0)
    dialog._delete()

    assert dialog.list.count() == 0
    assert session.image_assets == {}
    dialog.close()
