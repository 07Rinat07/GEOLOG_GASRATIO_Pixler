from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.adaptive_toolbar import AdaptiveActionToolBar
from geoworkbench.ui.masterlog_preview_dialog import MasterlogPreviewDialog


def test_masterlog_preview_dialog_uses_selected_template(qapp) -> None:
    template = MasterlogTemplate("standard", "Daily form")
    settings = MasterlogOutputSettings(100.0, 200.0, AppLanguage.EN)

    dialog = MasterlogPreviewDialog(
        template, ProjectSession(), language=AppLanguage.EN, settings=settings
    )

    assert dialog.windowTitle() == "Masterlog preview — Daily form"
    assert dialog.preview.template is template
    assert dialog.preview.settings is settings
    assert dialog.inspect_button.text() == "Inspect"
    assert dialog.lithology_button.text() == "Fill lithology"
    assert dialog.cuttings_button.text() == "Fill cuttings"
    assert dialog.description_button.text() == "Cuttings description"
    assert dialog.analysis_button.text() == "Calcimetry / LBA"
    assert dialog.stratigraphy_button.text() == "Stratigraphy"
    assert dialog.pin_button.text() == "Pin for PDF"
    assert not dialog.pin_button.isEnabled()
    assert dialog.callouts_button.text() == "Callouts..."
    dialog._set_mode("lithology")
    assert dialog.preview.selection_mode == "lithology"
    assert dialog.lithology_button.isChecked()
    dialog._set_mode("analysis")
    assert dialog.preview.selection_mode == "analysis"
    assert dialog.analysis_button.isChecked()
    dialog._set_mode("cuttings_description")
    assert dialog.preview.selection_mode == "cuttings_description"
    assert dialog.description_button.isChecked()
    dialog._set_mode("stratigraphy")
    assert dialog.preview.selection_mode == "stratigraphy"
    assert dialog.stratigraphy_button.isChecked()
    dialog.close()


def test_masterlog_preview_dialog_fits_work_area_and_uses_overflow_toolbar(qapp) -> None:
    dialog = MasterlogPreviewDialog(
        MasterlogTemplate("standard", "Adaptive"),
        ProjectSession(),
        language=AppLanguage.EN,
    )
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()

        toolbar = dialog.findChild(AdaptiveActionToolBar, "masterlog-preview-actions")
        assert toolbar is not None
        assert [action.text() for action in toolbar.actions() if action.text()] == [
            "Inspect",
            "Fill lithology",
            "Fill cuttings",
            "Cuttings description",
            "Calcimetry / LBA",
            "Stratigraphy",
            "Pin for PDF",
            "Callouts...",
        ]
        assert dialog.preview.minimumWidth() <= 320
        assert dialog.preview.minimumHeight() <= 240

        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        assert not toolbar.isAncestorOf(buttons)
    finally:
        dialog.close()
