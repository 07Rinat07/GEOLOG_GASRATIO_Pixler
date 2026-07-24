from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_constructor_assets_are_packaged_with_expected_counts() -> None:
    resource_root = ROOT / "src/geoworkbench/resources/constructor_assets"
    lithology = json.loads((resource_root / "lithology/manifest.json").read_text("utf-8"))
    symbols = json.loads((resource_root / "symbols/manifest.json").read_text("utf-8"))
    assert lithology["unique_asset_count"] == 117
    assert len(lithology["assets"]) == 117
    assert symbols["unique_asset_count"] == 19
    assert len(symbols["assets"]) == 19


def test_constructor_menu_and_dialog_are_in_actual_application_source() -> None:
    main_window = (ROOT / "src/geoworkbench/ui/main_window.py").read_text("utf-8")
    dialog = ROOT / "src/geoworkbench/ui/constructor_dialog.py"
    assert dialog.is_file()
    assert 'self._add_localized_menu("menu.constructor")' in main_window
    assert 'self._localized_action("constructor.open")' in main_window
    assert "def show_constructor" in main_window


def test_constructor_translation_keys_are_synchronized() -> None:
    required = {
        "menu.constructor",
        "constructor.open",
        "masterlog_symbols.offset_x",
        "masterlog_symbols.offset_y",
        "masterlog_header.legend_manual",
        "masterlog_header.legend_used_manual",
    }
    for language in ("ru", "kk", "en"):
        payload = json.loads(
            (ROOT / f"src/geoworkbench/resources/i18n/{language}.json").read_text("utf-8")
        )
        assert required <= payload.keys()


def test_constructor_documentation_is_synchronized() -> None:
    for language in ("ru", "kk", "en"):
        assert (ROOT / f"docs/{language}/FORM_CONSTRUCTOR_PLAN.md").is_file()
        assert (ROOT / f"docs/{language}/CONSTRUCTOR.md").is_file()


def test_constructor_does_not_reference_lag_projection_locals() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text("utf-8")
    constructor_body = source.split("    def show_constructor", 1)[1].split(
        "    def show_form_manager", 1
    )[0]
    assert "opened_from_projection" not in constructor_body
    assert "original_dataset_id" not in constructor_body
