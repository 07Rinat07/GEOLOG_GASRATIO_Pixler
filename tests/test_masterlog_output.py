import pytest

from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.masterlog_output_dialog import MasterlogOutputDialog


def test_masterlog_output_settings_validate_interval_and_language() -> None:
    settings = MasterlogOutputSettings(100.0, 200.0, AppLanguage.EN)

    assert settings.depth_range == (100.0, 200.0)
    with pytest.raises(ValueError):
        MasterlogOutputSettings(200.0, 100.0)


def test_masterlog_output_dialog_returns_selected_interval_and_language(qapp) -> None:
    dialog = MasterlogOutputDialog((100.0, 300.0), language=AppLanguage.EN)
    dialog.top_input.setValue(125.0)
    dialog.bottom_input.setValue(250.0)
    dialog.language_input.setCurrentIndex(dialog.language_input.findData(AppLanguage.KK.value))

    assert dialog.windowTitle() == "Masterlog output settings"
    assert dialog.settings() == MasterlogOutputSettings(125.0, 250.0, AppLanguage.KK)
    dialog.close()
