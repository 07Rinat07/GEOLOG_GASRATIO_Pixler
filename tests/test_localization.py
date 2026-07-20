from geoworkbench.services.localization import (
    AppLanguage,
    LanguageSettings,
    Localizer,
    load_catalog,
)
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
    assert window.default_tablet_action.text() == "Build default log display"
    assert window.normalize_depth_action.text() == "Create a copy with ascending depth..."
    assert window.ratio_action.text() == "Calculate basic Gas Ratios"
    tablet_menu_action = next(
        action for action in window.menuBar().actions() if action.text() == "Log layout"
    )
    tablet_menu = tablet_menu_action.menu()
    assert tablet_menu is not None
    tablet_labels = [action.text() for action in tablet_menu.actions()]
    assert "Add track" in tablet_labels
    assert "Show all hidden tracks" in tablet_labels
    assert "Set visible depth interval..." in tablet_labels
    assert "Show full depth range" in tablet_labels
    assert window.statusBar().currentMessage() == "Ready: import data"
    window.close()


def test_print_vocabulary_is_available_in_three_languages() -> None:
    assert Localizer.create(AppLanguage.RU).text("print.well") == "Скважина"
    assert Localizer.create(AppLanguage.KK).text("print.well") == "Ұңғыма"
    assert Localizer.create(AppLanguage.EN).text("print.well") == "Well"


def test_depth_directions_are_available_in_three_languages() -> None:
    assert Localizer.create(AppLanguage.RU).text("depth.direction.descending") == "по убыванию"
    assert Localizer.create(AppLanguage.KK).text("depth.direction.descending") == "кему ретімен"
    assert Localizer.create(AppLanguage.EN).text("depth.direction.descending") == "descending"


def test_language_switch_retranslates_open_interface_without_restart(qapp) -> None:
    storage = MemorySettings()
    window = MainWindow(
        language=AppLanguage.RU,
        language_settings=LanguageSettings(storage),
    )
    session = window.session
    project_controller = window.project_controller
    tablet_layout = window.tablet_view.layout_model

    window.change_language(AppLanguage.KK)

    kk = Localizer.create(AppLanguage.KK)
    assert window.language is AppLanguage.KK
    assert window.localizer.language is AppLanguage.KK
    assert window.session is session
    assert window.project_controller is project_controller
    assert window.tablet_view.layout_model is tablet_layout
    assert storage.values["ui/language"] == "kk"
    assert window.tabs.tabText(0) == kk.text("tab.curves")
    assert window.tabs.tabText(1) == kk.text("tab.table")
    assert window.tabs.tabText(2) == kk.text("tab.tablet")
    assert window.project_dock.windowTitle() == kk.text("dock.project")
    assert window.open_project_action.text() == kk.text("shell.open_project")
    assert window.open_data_action.text() == kk.text("import.universal")
    assert window.default_tablet_action.text() == kk.text("tablet.build_default")
    assert window.curve_browser.search_input.placeholderText() == kk.text("curve_browser.search")
    assert window.las_table_editor.hint.text() == kk.text("table.hint")
    assert window.inspector.apply_button.text() == kk.text("common.apply")
    assert window.interpretation_properties.manager_button.text() == kk.text(
        "interpretations.open_manager"
    )
    assert window.tablet_view._goto_button.text() == kk.text("tablet.goto")
    assert window.language_actions[AppLanguage.KK].isChecked()

    window.change_language(AppLanguage.EN)

    en = Localizer.create(AppLanguage.EN)
    assert window.language is AppLanguage.EN
    assert storage.values["ui/language"] == "en"
    assert window.open_project_action.text() == en.text("shell.open_project")
    assert window.tabs.tabText(2) == en.text("tab.tablet")
    assert window.curve_view.title_text == en.text("curve.empty")
    assert window.tablet_view._full_range_button.text() == en.text("tablet.full_range")
    assert window.language_actions[AppLanguage.EN].isChecked()
    window.close()
