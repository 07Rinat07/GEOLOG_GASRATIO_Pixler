from __future__ import annotations

from pathlib import Path

import pytest

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
    assert "QTimer.singleShot(120, self, self._update_toolbar_adaptation)" in source
    assert "screen.logicalDotsPerInchChanged.connect(self._on_toolbar_metrics_changed)" in source
    assert "screen.geometryChanged.connect(self._on_toolbar_metrics_changed)" in source
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
    assert "class _ResponsiveToolbarRow" in source
    assert "class _ResponsiveCommandBar(QFrame)" in source
    assert "self.main_toolbar.set_content_widget(self.main_toolbar_row)" in source
    assert "self.main_toolbar.addAction(self.home_action)" not in source
    assert "qt_toolbar_ext_button" not in source
    assert "def _responsive_row_required_width" in source
    measured = source[
        source.index("def _toolbar_required_width") : source.index(
            "def _measure_main_toolbar_mode"
        )
    ]
    assert "widget.isHidden()" not in measured
    assert source.count('("constructor", self.constructor_button)') == 1


def test_toolbar_uses_one_constrained_row_and_pins_edit_control_after_stretch() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")

    create = source[source.index("def _create_toolbar"):source.index("def toggle_cursor_line")]
    assert "self.main_toolbar_layout.addWidget(self.main_toolbar_spacer, 1)" in create
    assert "self.main_toolbar_layout.addWidget(self.edit_mode_button)" in create
    spacer_position = create.index(
        "self.main_toolbar_layout.addWidget(self.main_toolbar_spacer, 1)"
    )
    edit_position = create.index(
        "self.main_toolbar_layout.addWidget(self.edit_mode_button)"
    )
    assert spacer_position < edit_position
    assert "self.main_toolbar_overflow_button" in create
    assert "self.form_edit_toolbar.set_content_widget(self.form_edit_row)" in create


def test_composite_toolbar_keeps_pinned_button_inside_at_multiple_widths() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from geoworkbench.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    try:
        for width in (1920, 1536, 1366, 1024, 760):
            window.resize(width, 800)
            app.processEvents()
            window._update_toolbar_adaptation()
            app.processEvents()

            row_rect = window.main_toolbar_row.rect()
            edit_rect = window.edit_mode_button.geometry()
            assert edit_rect.left() >= row_rect.left()
            assert edit_rect.right() <= row_rect.right()

        narrow_width = window.main_toolbar_row.width()
        window.resize(1366, 800)
        app.processEvents()
        window._update_toolbar_adaptation()
        app.processEvents()
        assert window.main_toolbar_row.width() > narrow_width

        # The command frame owns the row directly and has no native toolbar
        # actions that could create Qt's private extension button.
        assert window.main_toolbar.layout().indexOf(window.main_toolbar_row) == 0
        assert window.main_toolbar.actions() == []
        assert window.home_button.iconSize().width() == 22
        assert (
            window._form_toolbar_buttons[window.annotation_symbol_action]
            .iconSize()
            .width()
            == 18
        )
    finally:
        window.close()
        app.processEvents()
