from __future__ import annotations

import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from geoworkbench.tablet.models import (
    CurveDisplaySettings,
    CurveStyle,
    TrackDefinition,
    TrackKind,
)
from geoworkbench.ui.adaptive_toolbar import AdaptiveActionToolBar
from geoworkbench.ui.skf_import_options_dialog import SkfImportMode
from geoworkbench.ui.tablet_track_preview_widget import TabletTrackPreviewWidget


def _application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return cast(QApplication, existing)
    return QApplication([])


def test_skf_import_modes_are_explicit_and_distinct() -> None:
    assert {mode.value for mode in SkfImportMode} == {
        "form_and_header",
        "form_only",
        "header_only",
    }


def test_adaptive_toolbar_action_remains_invokable() -> None:
    _application()
    calls: list[str] = []
    toolbar = AdaptiveActionToolBar()
    action = toolbar.add_standard_action("Apply", lambda: calls.append("applied"))

    action.trigger()

    assert calls == ["applied"]
    toolbar.close()


def test_tablet_track_preview_renders_header_grid_and_curve_offscreen() -> None:
    application = _application()
    track = TrackDefinition(
        track_id="preview-track",
        title="Газовые параметры",
        kind=TrackKind.CURVE,
        curve_mnemonics=["ROP"],
        width=260,
        group_title="Технология",
        curve_styles={"ROP": CurveStyle(color="#2563eb", width=1.5)},
        curve_display={
            "ROP": CurveDisplaySettings(
                display_name="Механическая скорость",
                x_min=0.0,
                x_max=100.0,
                header_text_color="#0f172a",
                header_line_color="#2563eb",
            )
        },
        grid_x=True,
        grid_y=True,
    )
    preview = TabletTrackPreviewWidget(track)
    preview.resize(440, 720)
    preview.show()
    application.processEvents()

    pixmap = preview.grab()

    assert not pixmap.isNull()
    assert pixmap.width() == 440
    assert pixmap.height() == 720
    preview.close()
