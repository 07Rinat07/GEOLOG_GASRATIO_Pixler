#!/usr/bin/env python3
"""Validate the Universal Constructor integration without importing PySide6."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    source_assets = ROOT / "resources/constructor_assets"
    package_assets = ROOT / "src/geoworkbench/resources/constructor_assets"
    for relative, expected in (
        (Path("lithology/manifest.json"), 117),
        (Path("symbols/manifest.json"), 19),
    ):
        source = json.loads((source_assets / relative).read_text("utf-8"))
        packaged = json.loads((package_assets / relative).read_text("utf-8"))
        require(source == packaged, f"Manifest copies differ: {relative}")
        require(len(source["assets"]) == expected, f"Unexpected asset count: {relative}")

    required_keys = {
        "menu.constructor",
        "constructor.open",
        "masterlog_symbols.offset_x",
        "masterlog_symbols.offset_y",
        "masterlog_header.legend_manual",
        "masterlog_header.legend_used_manual",
    }
    catalogs = []
    for language in ("ru", "kk", "en"):
        catalog = json.loads(
            (ROOT / f"src/geoworkbench/resources/i18n/{language}.json").read_text("utf-8")
        )
        require(required_keys <= catalog.keys(), f"Missing {language} constructor translations")
        catalogs.append(set(catalog))
    require(catalogs[0] == catalogs[1] == catalogs[2], "RU/KK/EN key sets differ")

    main_window = (ROOT / "src/geoworkbench/ui/main_window.py").read_text("utf-8")
    require('self._add_localized_menu("menu.constructor")' in main_window, "Menu not wired")
    require("def show_constructor" in main_window, "Constructor action handler not wired")
    require((ROOT / "src/geoworkbench/ui/constructor_dialog.py").is_file(), "Dialog missing")

    for language in ("ru", "kk", "en"):
        require((ROOT / f"docs/{language}/CONSTRUCTOR.md").is_file(), "Guide missing")
        require((ROOT / f"docs/{language}/FORM_CONSTRUCTOR_PLAN.md").is_file(), "Plan missing")

    print("Universal Constructor integration: OK")
    print("Lithotypes: 117")
    print("Depth symbols: 19")
    print("Languages: RU / KK / EN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
