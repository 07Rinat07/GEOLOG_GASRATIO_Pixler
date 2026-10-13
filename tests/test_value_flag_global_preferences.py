from dataclasses import replace
import json

import pytest
from PySide6.QtCore import QSettings

from geoworkbench.printing.print_job import PrintExportPreferences
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.user_profiles import UserProfileSettings
from geoworkbench.ui.print_center_dialog import PrintCenterDialog


@pytest.mark.parametrize("language", list(AppLanguage))
def test_global_value_switch_reopens_without_erasing_individual_selection(qapp, tmp_path, language):
    path = str(tmp_path / "engineers.ini")
    profiles = UserProfileSettings(QSettings(path, QSettings.Format.IniFormat))
    first = profiles.create("First")
    options = (("a", "TG: 15.5 %"), ("b", "C1: 10 %"))
    dialog = PrintCenterDialog(language=language, value_flag_options=options,
                               initial_value_flag_ids=("a",))
    try:
        dialog.print_value_flags_check.setChecked(False)
        assert dialog.job_settings(allow_missing_target=True).included_value_annotation_ids == ()
        assert dialog.selected_value_annotation_ids() == ("a",)
        preferences = dialog.preferences()
        profiles.save_print_export_preferences(preferences)
        profiles.save_print_export_preferences_for_form(
            "form-a", replace(preferences, print_value_flags_enabled=True),
        )
        profiles.create("Second")
        assert profiles.print_export_preferences().print_value_flags_enabled is True
        profiles = UserProfileSettings(QSettings(path, QSettings.Format.IniFormat))
        profiles.select(first.profile_id)
        assert profiles.print_export_preferences().print_value_flags_enabled is False
        assert profiles.print_export_preferences_for_form("form-a").print_value_flags_enabled is True
        assert profiles.print_export_preferences_for_form("form-b").print_value_flags_enabled is False
        reopened = PrintCenterDialog(language=language, value_flag_options=options,
                                     initial_value_flag_ids=("a",),
                                     initial_preferences=profiles.print_export_preferences())
        try:
            assert not reopened.print_value_flags_check.isChecked()
            assert reopened.job_settings(allow_missing_target=True).included_value_annotation_ids == ()
            reopened.print_value_flags_check.setChecked(True)
            assert reopened.job_settings(allow_missing_target=True).included_value_annotation_ids == ("a",)
            reopened.reject()
            assert profiles.print_export_preferences().print_value_flags_enabled is False
        finally:
            reopened.close()
    finally:
        dialog.close()


@pytest.mark.parametrize("raw", [None, "false", 0, [], {}])
def test_invalid_or_legacy_switch_keeps_other_preferences(qapp, tmp_path, raw):
    settings = QSettings(str(tmp_path / "legacy.ini"), QSettings.Format.IniFormat)
    profiles = UserProfileSettings(settings)
    profiles.create("Legacy")
    profiles.save_print_export_preferences(PrintExportPreferences(dpi=144))
    key = profiles._print_export_preferences_key()
    payload = json.loads(settings.value(key))
    if raw is None:
        payload.pop("print_value_flags_enabled")
    else:
        payload["print_value_flags_enabled"] = raw
    settings.setValue(key, json.dumps(payload))
    settings.sync()
    loaded = profiles.print_export_preferences()
    assert loaded.print_value_flags_enabled is True
    assert loaded.dpi == 144


@pytest.mark.parametrize("raw", [None, "false", 0, 1])
def test_switch_requires_a_real_boolean(raw):
    with pytest.raises(ValueError, match="boolean"):
        PrintExportPreferences(print_value_flags_enabled=raw)
