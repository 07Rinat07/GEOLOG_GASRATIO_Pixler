from __future__ import annotations

from pathlib import Path

from geoworkbench.ui.toolbar_adaptation import (
    choose_toolbar_adaptation,
    overflow_item_count,
    required_toolbar_width,
)


ROOT = Path(__file__).resolve().parents[1]


def test_toolbar_stays_expanded_only_when_measured_content_fits() -> None:
    mode = choose_toolbar_adaptation(2560, 2110, 980, 720)

    assert mode.compact is False
    assert mode.ultra_compact is False
    assert mode.fits_available_width is True


def test_1920_monitor_uses_compact_mode_when_localized_labels_are_wider() -> None:
    # This reproduces the desktop-monitor failure: the old fixed 1760-pixel
    # threshold kept labels visible even though the real Russian toolbar was
    # wider than the 1920-pixel logical work area.
    mode = choose_toolbar_adaptation(1920, 2110, 980, 720)

    assert mode.compact is True
    assert mode.ultra_compact is False
    assert mode.required_width == 980


def test_toolbar_uses_logical_widths_for_scaled_monitor_and_laptop() -> None:
    desktop_at_125_percent = choose_toolbar_adaptation(1536, 2110, 980, 720)
    laptop = choose_toolbar_adaptation(1366, 2110, 980, 720)
    narrow_window = choose_toolbar_adaptation(760, 2110, 980, 620)

    assert desktop_at_125_percent == laptop
    assert desktop_at_125_percent.compact is True
    assert desktop_at_125_percent.ultra_compact is False
    assert narrow_window.ultra_compact is True


def test_toolbar_uses_hysteresis_when_restoring_labels() -> None:
    still_compact = choose_toolbar_adaptation(
        2160,
        2110,
        980,
        720,
        currently_compact=True,
        restore_margin=72,
    )
    restored = choose_toolbar_adaptation(
        2220,
        2110,
        980,
        720,
        currently_compact=True,
        restore_margin=72,
    )

    assert still_compact.compact is True
    assert restored.compact is False


def test_required_width_reserves_spacing_and_native_toolbar_chrome() -> None:
    assert required_toolbar_width([100, 80, 60], spacing=6, chrome_width=40) == 292


def test_main_window_measures_actual_modes_and_rechecks_after_screen_change() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")

    assert "def _toolbar_required_width" in source
    assert "def _measure_main_toolbar_mode" in source
    assert "def _measure_form_toolbar_mode" in source
    assert "handle.screenChanged.connect(self._on_window_screen_changed)" in source
    assert "QTimer.singleShot(120, self._update_toolbar_adaptation)" in source
    assert "self.main_toolbar_spacer" in source
    assert "1760" not in source[source.index("def _create_toolbar"):source.index("def toggle_cursor_line")]


def test_overflow_fallback_hides_low_priority_items_until_pinned_control_fits() -> None:
    count = overflow_item_count(
        900,
        1160,
        [82, 76, 70, 66, 64],
        overflow_button_width=40,
        safety_margin=20,
    )

    assert count == 5


def test_overflow_fallback_is_not_used_when_ultra_compact_row_fits() -> None:
    assert overflow_item_count(1000, 930, [80, 70, 60]) == 0


def test_main_toolbar_has_dpi_watchers_and_real_overflow_menu() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")

    assert "logicalDotsPerInchChanged.connect" in source
    assert "availableGeometryChanged.connect" in source
    assert "def _fit_main_toolbar_overflow" in source
    assert "mainToolbarOverflowButton" in source
    assert "self.edit_mode_button" in source
    assert "self._main_toolbar_overflow_candidates" in source
    assert "native QToolBar layout may already hide overflowing widgets" in source
    assert "widget.isHidden()" not in source[source.index("def _toolbar_required_width"):source.index("def _measure_main_toolbar_mode")]
    assert source.count('("constructor", self.constructor_button)') == 1
