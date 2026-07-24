from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_working_curve_header_has_fixed_geometry_and_no_scale_selector() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )

    assert "CURVE_HEADER_LABEL_HEIGHT = CURVE_HEADER_EDITOR_HEIGHT" in source
    assert "self.setFixedHeight(CURVE_HEADER_EDITOR_HEIGHT)" in source
    assert "self.scale = QComboBox()" not in source
    assert "self._scale = spec.scale" in source
    assert "Linear or\n    logarithmic mode is deliberately absent" in source


def test_engineering_ruler_draws_contrast_caption_ticks_and_mandatory_endpoints() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )

    assert 'caption += f" · {self._unit}"' in source
    assert 'QPen(QColor("#334155"), 3.0)' in source
    assert "ruler_color.lightness() > 176" in source
    assert "labelled.extend((major_lines[0], major_lines[-1]))" in source
    assert "metrics.elidedText" in source
    assert 'curve_settings.header_scale_caption' in source


def test_curve_hover_and_pencil_readout_use_human_readable_identity() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )

    assert "def _curve_pencil_display_label" in source
    assert 'return f"{display_name} [{mnemonic}]"' in source
    assert 'item.setToolTip(' in source
    assert 'upper_curve.setToolTip(tooltip)' in source
    assert 'curve=self._curve_pencil_display_label()' in source


def test_application_forces_readable_tooltip_palette() -> None:
    source = (ROOT / "src/geoworkbench/app/main.py").read_text(encoding="utf-8")

    assert "def _configure_readable_tooltips" in source
    assert "QPalette.ColorRole.ToolTipBase" in source
    assert "QPalette.ColorRole.ToolTipText" in source
    assert "QToolTip { color:#0f172a; background-color:#fffbe6;" in source
    assert "_configure_readable_tooltips(app)" in source


def test_toolbar_help_labels_do_not_inherit_opaque_white_backgrounds() -> None:
    tablet = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )
    window = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(
        encoding="utf-8"
    )

    assert 'background:transparent; color:#64748b; font-size:10px;' in tablet
    assert 'background:transparent; color:#9a3412;' in tablet
    assert 'background:transparent; font-weight:700; color:#1e3a8a;' in window


def test_localizations_expose_scale_caption_and_curve_identity_placeholder() -> None:
    for language in ("ru", "kk", "en"):
        payload = json.loads(
            (ROOT / f"src/geoworkbench/resources/i18n/{language}.json").read_text(
                encoding="utf-8"
            )
        )
        assert payload["curve_settings.header_scale_caption"]
        assert "{curve}" in payload["tablet.curve_pencil_active"]
        assert "{curve}" in payload["tablet.curve_pencil_live_readout"]
        assert "{mnemonic}" not in payload["tablet.curve_pencil_live_readout"]
