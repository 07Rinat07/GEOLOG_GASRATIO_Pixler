from __future__ import annotations

from pathlib import Path

from geoworkbench.ui.toolbar_adaptation import choose_toolbar_adaptation


ROOT = Path(__file__).resolve().parents[1]


def test_toolbar_stays_expanded_when_content_fits() -> None:
    mode = choose_toolbar_adaptation(1920, 1760)
    assert mode.compact is False
    assert mode.ultra_compact is False


def test_toolbar_switches_to_compact_before_right_side_is_clipped() -> None:
    mode = choose_toolbar_adaptation(1672, 1760)
    assert mode.compact is True
    assert mode.ultra_compact is False


def test_toolbar_uses_hysteresis_and_ultra_compact_mode() -> None:
    still_compact = choose_toolbar_adaptation(
        1800, 1760, currently_compact=True, restore_margin=96
    )
    restored = choose_toolbar_adaptation(
        1900, 1760, currently_compact=True, restore_margin=96
    )
    narrow = choose_toolbar_adaptation(900, 1760)

    assert still_compact.compact is True
    assert restored.compact is False
    assert narrow.compact is True
    assert narrow.ultra_compact is True


def test_main_window_wires_responsive_modes_for_both_top_toolbars() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")

    assert "QTimer.singleShot(0, self._update_toolbar_adaptation)" in source
    assert "def _apply_main_toolbar_mode" in source
    assert "def _apply_form_toolbar_mode" in source
    assert "self.edit_mode_button.setToolButtonStyle" in source
    assert "self.form_edit_toolbar.setToolButtonStyle" in source
    assert "self.main_toolbar.setMinimumWidth(0)" in source
    assert "self.form_edit_toolbar.setMinimumWidth(0)" in source
