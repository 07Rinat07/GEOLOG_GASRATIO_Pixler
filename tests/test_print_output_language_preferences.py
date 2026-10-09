from dataclasses import replace
import json

import pytest
from PySide6.QtCore import QSettings

from geoworkbench.printing.print_job import (
    PrintExportPreferences,
    PrintJobSettings,
    PrintOutputFormat,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.user_profiles import UserProfileSettings
from geoworkbench.ui.print_center_dialog import PrintCenterDialog


@pytest.mark.parametrize("language", list(AppLanguage))
def test_language_preferences_survive_ini_reopen_and_remain_scoped(qapp, tmp_path, language):
    path = str(tmp_path / "engineers.ini")
    profiles = UserProfileSettings(QSettings(path, QSettings.Format.IniFormat))
    first = profiles.create("First")
    selected = PrintExportPreferences(output_language=language, dpi=144)
    profiles.save_print_export_preferences(selected)
    profiles.save_print_export_preferences_for_form(
        "form-a", replace(selected, output_language=AppLanguage.KK)
    )
    profiles.save_print_export_preferences_for_form(
        "form-b", replace(selected, output_language=AppLanguage.RU)
    )
    second = profiles.create("Second")
    profiles.save_print_export_preferences(
        PrintExportPreferences(output_language=AppLanguage.EN, dpi=300)
    )
    reopened = UserProfileSettings(QSettings(path, QSettings.Format.IniFormat))
    assert reopened.active().profile_id == second.profile_id
    assert reopened.print_export_preferences().output_language == AppLanguage.EN
    assert reopened.print_export_preferences_for_form("form-a").output_language == AppLanguage.EN
    reopened.select(first.profile_id)
    assert reopened.print_export_preferences() == selected
    assert reopened.print_export_preferences_for_form("form-a").output_language == AppLanguage.KK
    assert reopened.print_export_preferences_for_form("form-b").output_language == AppLanguage.RU
    assert reopened.print_export_preferences_for_form("unconfigured").output_language == language


@pytest.mark.parametrize(
    "raw_language", ["missing", None, "invalid", False, 42, {"en": True}, ["ru"]]
)
def test_legacy_or_invalid_language_preserves_other_preferences(qapp, tmp_path, raw_language):
    storage = QSettings(str(tmp_path / "legacy.ini"), QSettings.Format.IniFormat)
    profiles = UserProfileSettings(storage)
    profiles.create("Legacy engineer")
    profiles.save_print_export_preferences(PrintExportPreferences(dpi=144, image_quality=80))
    key = profiles._print_export_preferences_key()
    payload = json.loads(storage.value(key))
    if raw_language == "missing":
        payload.pop("output_language")
    else:
        payload["output_language"] = raw_language
    storage.setValue(key, json.dumps(payload))
    storage.sync()
    loaded = UserProfileSettings(
        QSettings(str(tmp_path / "legacy.ini"), QSettings.Format.IniFormat)
    ).print_export_preferences()
    assert loaded.output_language is None
    assert loaded.dpi == 144
    assert loaded.image_quality == 80
    for ui_language in AppLanguage:
        dialog = PrintCenterDialog(language=ui_language, initial_preferences=loaded)
        try:
            assert dialog.report_output_language.currentData() == ui_language
            assert dialog.preferences().output_language == ui_language
        finally:
            dialog.close()


@pytest.mark.parametrize("invalid", ["ru", "EN", False, 42, {}, [], object()])
@pytest.mark.parametrize("model", [PrintExportPreferences, PrintJobSettings])
def test_settings_reject_invalid_typed_language(model, invalid):
    kwargs = {"output_language": invalid}
    if model is PrintJobSettings:
        kwargs["output_format"] = PrintOutputFormat.PRINTER
    with pytest.raises(ValueError, match="Язык отчёта"):
        model(**kwargs)


@pytest.mark.parametrize("included", [None, ("depth",)])
def test_preflight_retains_strict_unicode_and_restores_column_mode(qapp, included):
    from geoworkbench.printing.document_export import _unicode_preflight
    from geoworkbench.printing.document_renderer import PrintDocumentContext
    from geoworkbench.printing.unicode_support import UnicodePrintError
    from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
    from geoworkbench.tablet.tablet_view import TabletView
    from test_interpretation_report import _session

    view = TabletView()
    view.set_layout_and_dataset(
        TabletLayout(
            tracks=[
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=100),
                TrackDefinition(
                    "bad", "Damaged \ufffd", TrackKind.CURVE, width=180, curve_mnemonics=["C1"]
                ),
            ]
        ),
        _session().current_dataset,
    )
    view.show()
    qapp.processEvents()
    try:
        job = PrintJobSettings(output_format=PrintOutputFormat.PRINTER, included_track_ids=included)
        if included is None:
            with pytest.raises(UnicodePrintError):
                _unicode_preflight(view, PrintDocumentContext("Report"), job)
        else:
            _unicode_preflight(view, PrintDocumentContext("Report"), job)
        assert all(not track.widget._print_mode for track in view.printable_tracks())
    finally:
        view.close()
        view.deleteLater()
        qapp.processEvents()
