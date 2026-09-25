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
    assert "Linear" in source
    assert "logarithmic mode is deliberately absent" in source


def test_engineering_ruler_uses_curve_name_without_generic_scale_caption() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )

    assert "curve_caption=title" in source
    assert "self._curve_caption = str(curve_caption).strip()" in source
    assert 'caption += f" · {self._unit}"' in source
    assert "painter.fontMetrics().elidedText" in source
    assert 'QPen(QColor("#334155"), 3.0)' in source
    assert "ruler_color.lightness() > 176" in source
    assert "labelled.extend((major_lines[0], major_lines[-1]))" in source
    assert "metrics.elidedText" in source
    assert 'curve_settings.header_scale_caption' not in source
    assert "action_strip.setFixedSize(14, 28)" in source


def test_curve_hover_and_pencil_readout_use_human_readable_identity() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )

    assert "def _curve_pencil_display_label" in source
    assert 'return f"{display_name} [{mnemonic}]"' in source
    assert 'item.setToolTip(' in source
    assert 'upper_curve.setToolTip(tooltip)' in source
    assert 'curve=self._curve_pencil_display_label()' in source


def test_application_uses_palette_aware_shared_tooltip_style() -> None:
    entrypoint = (ROOT / "src/geoworkbench/app/main.py").read_text(encoding="utf-8")
    shared_style = (ROOT / "src/geoworkbench/ui/application_style.py").read_text(
        encoding="utf-8"
    )

    assert "apply_adaptive_application_style(app)" in entrypoint
    assert "_configure_readable_tooltips" not in entrypoint
    assert "QPalette.ColorRole.ToolTipBase" not in entrypoint
    assert "QPalette.ColorRole.ToolTipText" not in entrypoint
    assert "QToolTip {" in shared_style
    assert "color: palette(text);" in shared_style
    assert "background-color: palette(base);" in shared_style
    assert "border: 1px solid palette(mid);" in shared_style


def test_toolbar_help_labels_do_not_inherit_opaque_white_backgrounds() -> None:
    tablet = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )
    window = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(
        encoding="utf-8"
    )
    shared_style = (ROOT / "src/geoworkbench/ui/application_style.py").read_text(
        encoding="utf-8"
    )

    assert 'background:transparent; color:#64748b; font-size:10px;' in tablet
    assert 'background:transparent; color:#9a3412;' in tablet
    assert 'self.form_edit_caption.setObjectName("formEditToolbarCaption")' in window
    assert "QLabel#formEditToolbarCaption" in shared_style
    assert "color: palette(window-text);" in shared_style


def test_localizations_preserve_curve_identity_placeholder() -> None:
    for language in ("ru", "kk", "en"):
        payload = json.loads(
            (ROOT / f"src/geoworkbench/resources/i18n/{language}.json").read_text(
                encoding="utf-8"
            )
        )
        assert "{curve}" in payload["tablet.curve_pencil_active"]
        assert "{curve}" in payload["tablet.curve_pencil_live_readout"]
        assert "{mnemonic}" not in payload["tablet.curve_pencil_live_readout"]
        assert "{old}" in payload["tablet.curve_pencil_live_readout"]
        assert "{value}" in payload["tablet.curve_pencil_live_readout"]
        assert "{delta}" in payload["tablet.curve_pencil_live_readout"]


def test_curve_pencil_toolbar_is_palette_aware_and_compact_when_disabled() -> None:
    tablet = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )
    shared_style = (ROOT / "src/geoworkbench/ui/application_style.py").read_text(
        encoding="utf-8"
    )

    assert 'self._curve_pencil_bar.setProperty("pencilActive", self._curve_pencil_enabled)' in tablet
    assert 'self._curve_pencil_status.setProperty("statusRole", "muted")' in tablet
    assert 'self._curve_pencil_status.setProperty("statusRole", "active")' in tablet
    assert 'self._curve_pencil_status.setProperty("statusRole", "error")' in tablet
    assert 'widget.setVisible(enabled)' in tablet
    assert 'self._curve_pencil_scroll.horizontalScrollBar().setValue(0)' in tablet
    assert "background:#fff7ed" not in tablet
    assert "background:#f8fafc" not in tablet[tablet.index("def _update_curve_pencil_bar_style"):tablet.index("def mark_curve_pencil_unsaved")]
    assert "QFrame#tabletCurvePencilBar" in shared_style
    assert 'QFrame#tabletCurvePencilBar[pencilActive="true"]' in shared_style
    assert 'QLabel[statusRole="muted"]' in shared_style


def test_single_curve_track_title_uses_human_readable_curve_identity() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )

    assert "if len(definition.curve_mnemonics) == 1:" in source
    assert "curve = self._dataset.curve_by_mnemonic(mnemonic)" in source
    assert "display = self._curve_display_name(definition, mnemonic, curve).strip()" in source
    assert 'return f"{display} [{mnemonic}]"' in source
