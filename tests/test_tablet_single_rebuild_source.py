from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _method_body(source: str, name: str, next_name: str) -> str:
    start = source.index(f"    def {name}(")
    end = source.index(f"    def {next_name}(", start)
    return source[start:end]


def test_large_tablet_actions_use_single_layout_dataset_render_transaction() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(
        encoding="utf-8"
    )

    recovery = _method_body(
        source,
        "_show_import_recovery_workspace",
        "_recovery_component_diagnostic",
    )
    browser = _method_body(
        source,
        "_build_tablet_from_curve_selection",
        "_add_curves_from_browser",
    )
    preset = _method_body(
        source,
        "apply_tablet_preset",
        "delete_tablet_preset",
    )

    assert "set_layout_and_dataset(TabletLayout(), None)" in recovery
    assert "set_layout_model(" not in recovery
    assert "set_dataset(None)" not in recovery

    assert "set_layout_and_dataset(" in browser
    assert "set_layout_model(" not in browser
    assert "set_dataset(self.session.current_dataset)" not in browser

    assert "set_layout_and_dataset(" in preset
    assert "set_layout_model(" not in preset
    assert "set_dataset(self.session.current_dataset)" not in preset
