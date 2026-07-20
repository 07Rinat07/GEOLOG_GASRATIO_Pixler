import json

import pytest

from geoworkbench.data.number_format import NumberDisplayFormat, NumberFormatMode
from geoworkbench.printing.page_settings import (
    PrintOrientation,
    PrintPageFormat,
    PrintPageSettings,
)
from geoworkbench.services.user_profiles import (
    CursorLineSettings,
    EngineerProfile,
    UserProfileSettings,
)


class MemorySettings:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def value(self, key: str, default: str = "") -> str:
        return self.values.get(key, default)

    def setValue(self, key: str, value: str) -> None:  # noqa: N802
        self.values[key] = value

    def remove(self, key: str) -> None:
        self.values.pop(key, None)

    def sync(self) -> None:
        pass


def test_profiles_are_named_persistent_and_selectable() -> None:
    storage = MemorySettings()
    settings = UserProfileSettings(storage)
    rinat = settings.create("Rinat Sarmuldin", "GeoLog")
    other = settings.create("Other Engineer", "Customer")

    assert settings.active() == other
    assert settings.select(rinat.profile_id) == rinat
    assert UserProfileSettings(storage).active() == rinat
    assert {item.display_name for item in settings.profiles()} == {
        "Rinat Sarmuldin",
        "Other Engineer",
    }


def test_delete_active_profile_selects_remaining_profile() -> None:
    settings = UserProfileSettings(MemorySettings())
    first = settings.create("First")
    second = settings.create("Second")
    settings.delete(second.profile_id)
    assert settings.active() == first


def test_update_preserves_stable_id() -> None:
    settings = UserProfileSettings(MemorySettings())
    profile = settings.create("Engineer")
    updated = settings.update(EngineerProfile(profile.profile_id, "Engineer 1", "Operator"))
    assert updated.profile_id == profile.profile_id
    assert settings.active() == updated


def test_invalid_or_corrupt_profiles_do_not_break_startup() -> None:
    storage = MemorySettings()
    storage.values["users/profiles"] = "not-json"
    assert UserProfileSettings(storage).profiles() == ()
    storage.values["users/profiles"] = json.dumps([{"profile_id": "x", "display_name": ""}])
    assert UserProfileSettings(storage).profiles() == ()


def test_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="Имя инженера"):
        UserProfileSettings(MemorySettings()).create("   ")


def test_print_page_settings_persist_per_active_profile() -> None:
    storage = MemorySettings()
    settings = UserProfileSettings(storage)
    first = settings.create("First")
    first_page = PrintPageSettings(
        PrintPageFormat.CUSTOM, PrintOrientation.LANDSCAPE, 420.0, 1200.0
    )
    settings.save_print_page_settings(first_page)
    second = settings.create("Second")

    assert settings.print_page_settings() == PrintPageSettings()
    settings.save_print_page_settings(
        PrintPageSettings(PrintPageFormat.A4, PrintOrientation.LANDSCAPE)
    )
    settings.select(first.profile_id)
    assert settings.print_page_settings() == first_page
    settings.select(second.profile_id)
    assert settings.print_page_settings().orientation is PrintOrientation.LANDSCAPE


def test_corrupt_print_page_settings_fall_back_to_defaults() -> None:
    storage = MemorySettings()
    storage.values["users/print_page/default"] = '{"page_format": "letter"}'

    assert UserProfileSettings(storage).print_page_settings() == PrintPageSettings()


def test_cursor_line_settings_persist_per_active_profile() -> None:
    storage = MemorySettings()
    settings = UserProfileSettings(storage)

    settings.save_cursor_line_settings(CursorLineSettings("#123456", 3.5, True))

    assert UserProfileSettings(storage).cursor_line_settings() == CursorLineSettings(
        "#123456", 3.5, True
    )
    profile = settings.create("Engineer")
    assert settings.cursor_line_settings() == CursorLineSettings()
    settings.save_cursor_line_settings(CursorLineSettings("#abcdef", 1.0, False))
    settings.select(profile.profile_id)
    assert settings.cursor_line_settings().color == "#abcdef"


def test_corrupt_cursor_line_settings_fall_back_to_defaults() -> None:
    storage = MemorySettings()
    storage.values["users/cursor_line/default"] = '{"color":"red","width":99}'

    assert UserProfileSettings(storage).cursor_line_settings() == CursorLineSettings()


def test_table_number_formats_persist_per_active_profile() -> None:
    storage = MemorySettings()
    settings = UserProfileSettings(storage)
    default_format = NumberDisplayFormat(NumberFormatMode.FIXED, 7)
    settings.save_table_number_formats({"curve:c2": default_format})

    profile = settings.create("Engineer")

    assert settings.table_number_formats() == {}
    profile_format = NumberDisplayFormat(NumberFormatMode.SCIENTIFIC, 3)
    settings.save_table_number_formats({"curve:ic4": profile_format})
    assert UserProfileSettings(storage).table_number_formats() == {"curve:ic4": profile_format}
    settings.delete(profile.profile_id)
    assert settings.table_number_formats() == {"curve:c2": default_format}


def test_corrupt_table_number_formats_are_ignored() -> None:
    storage = MemorySettings()
    storage.values["users/table_number_formats/default"] = json.dumps(
        {
            "curve:c1": {"mode": "fixed", "precision": 6},
            "curve:c2": {"mode": "unknown", "precision": 6},
            "curve:c3": {"mode": "adaptive", "precision": 0},
        }
    )

    assert UserProfileSettings(storage).table_number_formats() == {
        "curve:c1": NumberDisplayFormat(NumberFormatMode.FIXED, 6)
    }


def test_print_export_preferences_roundtrip() -> None:
    from geoworkbench.printing.print_job import PrintExportPreferences, PrintOutputFormat

    storage = MemorySettings()
    settings = UserProfileSettings(storage)
    expected = PrintExportPreferences(
        output_format=PrintOutputFormat.JPEG,
        dpi=600,
        image_quality=84,
    )

    settings.save_print_export_preferences(expected)

    assert settings.print_export_preferences() == expected
