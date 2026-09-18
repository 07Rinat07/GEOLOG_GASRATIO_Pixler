from geoworkbench.importers.gs2 import Gs2ContainerError
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import gs2_import_dialog as gs2_dialog_module
from geoworkbench.ui.gs2_import_dialog import Gs2ImportDialog


def test_gs2_import_dialog_fits_work_area_on_invalid_container(
    qapp,
    tmp_path,
    monkeypatch,
) -> None:
    source = tmp_path / "invalid.gs2"
    source.write_bytes(b"not-a-gs2-container")

    def fail_inspection(_source):
        raise Gs2ContainerError("invalid container")

    monkeypatch.setattr(gs2_dialog_module, "inspect_gs2", fail_inspection)
    dialog = Gs2ImportDialog(source, language=AppLanguage.EN)
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()
        assert not dialog.ok_button.isEnabled()
    finally:
        dialog.close()
