from __future__ import annotations

import json
from pathlib import Path

from geoworkbench.tablet.header_geometry import (
    CURVE_HEADER_BOTTOM_CLEARANCE,
    CURVE_HEADER_PRINT_ROW_HEIGHT,
    CURVE_HEADER_ROW_HEIGHT,
    align_curve_header_band_height,
    curve_header_content_height,
    curve_header_viewport_height,
)


ROOT = Path(__file__).resolve().parents[1]
TABLET_VIEW = ROOT / "src/geoworkbench/tablet/tablet_view.py"


def test_parameter_header_keeps_complete_rows_and_bottom_clearance() -> None:
    assert CURVE_HEADER_ROW_HEIGHT == 44
    assert CURVE_HEADER_BOTTOM_CLEARANCE == 8
    assert curve_header_content_height(6) == 6 * 44 + 8
    assert curve_header_viewport_height(9) == 7 * 44 + 8
    # A partial seventh row is rounded upward instead of clipping it away.
    assert align_curve_header_band_height(6 * 44 + 43) == 7 * 44 + 8


def test_ruler_uses_parameter_identity_and_keeps_both_actions() -> None:
    source = TABLET_VIEW.read_text(encoding="utf-8")

    assert "curve_caption=title" in source
    assert "self._curve_caption = str(curve_caption).strip()" in source
    assert 'caption += f" · {self._unit}"' in source
    assert "action_strip.setFixedSize(14, 28)" in source
    assert 'self.auto_button.setText("A")' in source
    assert 'self.settings_button.setText("⚙")' in source
    assert 'f"{ruler_identity} [{mnemonic}]\\n{spec.scale_tooltip}"' in source
    assert "self.title_label = QLabel(title)" not in source
    assert "curve_settings.header_scale_caption" not in source


def test_every_form_path_reuses_the_same_curve_header_editor() -> None:
    source = TABLET_VIEW.read_text(encoding="utf-8")
    assert "class TabletTrackWidget(QFrame):" in source
    assert "label = CurveHeaderEditor(" in source
    assert "def _create_rendered_track(" in source
    assert "track = TabletTrackWidget(" in source
    assert "rendered.widget.set_curve_headers(header_rows, header_ranges)" in source
    assert "track.set_curve_headers(header_rows, header_ranges)" in source


def test_removed_scale_caption_key_is_absent_from_every_catalog() -> None:
    for language in ("ru", "kk", "en"):
        path = ROOT / f"src/geoworkbench/resources/i18n/{language}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert "curve_settings.header_scale_caption" not in payload
        assert payload["curve_settings.header_scale_tooltip"].strip()


def test_print_parameter_rows_have_real_internal_and_trailing_space() -> None:
    assert CURVE_HEADER_ROW_HEIGHT < CURVE_HEADER_PRINT_ROW_HEIGHT == 52
    assert curve_header_viewport_height(
        6,
        row_height=CURVE_HEADER_PRINT_ROW_HEIGHT,
    ) == 6 * CURVE_HEADER_PRINT_ROW_HEIGHT + CURVE_HEADER_BOTTOM_CLEARANCE


def test_print_ruler_uses_enlarged_typography_without_changing_screen_defaults() -> None:
    source = TABLET_VIEW.read_text(encoding="utf-8")
    assert "caption_font.setPixelSize(10 if self._print_mode else 8)" in source
    assert "value_font.setPixelSize(9 if self._print_mode else 8)" in source
    assert "self.setFixedHeight(30 if self._print_mode else 28)" in source
    assert "item.widget.print_curve_header_height" in (
        ROOT / "src/geoworkbench/printing/document_renderer.py"
    ).read_text(encoding="utf-8")


def test_print_typography_is_enabled_before_snapshot_geometry_is_measured() -> None:
    source = (
        ROOT / "src/geoworkbench/printing/tablet_print.py"
    ).read_text(encoding="utf-8")
    enable_position = source.index("item.widget.set_print_mode(True)")
    measure_position = source.index(
        "content_height = max(item.widget.height() for item in rendered)",
        enable_position,
    )
    assert enable_position < measure_position
    assert "item.widget.set_synchronized_header_height(print_header_band)" in source
