from geoworkbench.services.localization import AppLanguage, LanguageSettings, Localizer, load_catalog
from geoworkbench.ui.main_window import MainWindow


class MemorySettings:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def value(self, key: str):
        return self.values.get(key)

    def setValue(self, key: str, value: str) -> None:  # noqa: N802
        self.values[key] = value

    def sync(self) -> None:
        pass


def test_all_language_catalogs_have_identical_non_empty_keys() -> None:
    catalogs = {language: load_catalog(language) for language in AppLanguage}
    expected = set(catalogs[AppLanguage.RU])

    assert expected
    assert all(set(catalog) == expected for catalog in catalogs.values())
    assert all(value.strip() for catalog in catalogs.values() for value in catalog.values())


def test_language_settings_round_trip_and_reject_unknown_value() -> None:
    storage = MemorySettings()
    settings = LanguageSettings(storage)

    assert settings.current() is None
    settings.save(AppLanguage.KK)
    assert settings.current() is AppLanguage.KK
    storage.values["ui/language"] = "unknown"
    assert settings.current() is None


def test_main_window_uses_selected_language_for_shell(qapp) -> None:
    window = MainWindow(
        language=AppLanguage.EN,
        language_settings=LanguageSettings(MemorySettings()),
    )

    assert window.tabs.tabText(0) == "LAS / Gas curves"
    assert window.open_data_action.text() == "Import data..."
    assert window.statusBar().currentMessage() == "Ready: import data"
    window.close()


def test_print_vocabulary_is_available_in_three_languages() -> None:
    assert Localizer.create(AppLanguage.RU).text("print.well") == "Скважина"
    assert Localizer.create(AppLanguage.KK).text("print.well") == "Ұңғыма"
    assert Localizer.create(AppLanguage.EN).text("print.well") == "Well"
