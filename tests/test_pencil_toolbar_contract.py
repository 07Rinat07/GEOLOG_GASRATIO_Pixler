from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TABLET = ROOT / "src/geoworkbench/tablet/tablet_view.py"
MAIN = ROOT / "src/geoworkbench/ui/main_window.py"
I18N = ROOT / "src/geoworkbench/resources/i18n"


def test_pencil_cursor_is_compact_and_uses_tip_hotspot() -> None:
    source = TABLET.read_text(encoding="utf-8")
    assert "pixmap = QPixmap(26, 26)" in source
    assert "return QCursor(pixmap, 3, 23)" in source


def test_connect_points_and_history_controls_are_explicit() -> None:
    source = TABLET.read_text(encoding="utf-8")
    assert "_curve_pencil_points_button" in source
    assert "CurvePencilMode.CONNECT_POINTS" in source
    assert "_curve_pencil_undo_button" in source
    assert "_curve_pencil_redo_button" in source
    assert "curve_pencil_undo_requested = Signal()" in source
    assert "curve_pencil_redo_requested = Signal()" in source


def test_curve_undo_redo_shortcuts_are_application_wide() -> None:
    source = MAIN.read_text(encoding="utf-8")
    assert source.count("Qt.ShortcutContext.ApplicationShortcut") >= 2
    assert "curve_pencil_undo_requested.connect(self.undo_curve_edit)" in source
    assert "curve_pencil_redo_requested.connect(self.redo_curve_edit)" in source
    assert "set_curve_pencil_history_state(can_undo, can_redo)" in source


def test_new_pencil_labels_exist_in_all_languages() -> None:
    required = {
        "tablet.curve_pencil_mode_freehand_button",
        "tablet.curve_pencil_mode_points_button",
        "tablet.curve_pencil_undo",
        "tablet.curve_pencil_redo",
        "tablet.curve_pencil_undo_context",
        "tablet.curve_pencil_redo_context",
    }
    for language in ("ru", "kk", "en"):
        payload = json.loads((I18N / f"{language}.json").read_text(encoding="utf-8"))
        assert required <= payload.keys()


def test_saving_does_not_destroy_curve_undo_history() -> None:
    source = TABLET.read_text(encoding="utf-8")
    block = source.split("def clear_curve_pencil_unsaved", 1)[1].split("def ", 1)[0]
    assert "history" in block.lower()
    assert "set_curve_pencil_history_state(False, False)" not in block
