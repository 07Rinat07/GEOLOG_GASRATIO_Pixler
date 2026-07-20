from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.masterlog_page_dialog import MasterlogPageDialog


def test_masterlog_page_dialog_edits_custom_geometry(qapp) -> None:
    template = MasterlogTemplate("standard", "Standard", page_format="A4")
    dialog = MasterlogPageDialog(template, language=AppLanguage.EN)
    dialog.format_input.setCurrentIndex(dialog.format_input.findData("custom"))
    dialog.orientation_input.setCurrentIndex(dialog.orientation_input.findData("landscape"))
    dialog.scale_input.setValue(250)
    dialog.header_input.setValue(30.0)
    dialog.width_input.setValue(250.0)
    dialog.height_input.setValue(500.0)

    assert dialog.windowTitle() == "Masterlog form settings"
    assert dialog.values() == ("custom", "landscape", 250, 30.0, 250.0, 500.0)
    assert not dialog.width_input.isHidden()
    dialog.close()
