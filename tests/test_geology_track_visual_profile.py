from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPen

from geoworkbench.printing import geology_track_rendering as renderer
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile


@pytest.mark.parametrize("grayscale", [False, True])
def test_geology_track_neutral_chrome_uses_profile_without_recoloring_semantics(qapp, monkeypatch, grayscale):
    visual = modern_oilfield_report_profile(grayscale=grayscale)
    palette = replace(visual.palette, border_strong="#102030", border="#405060", text_secondary="#708090", text="#123456")
    monkeypatch.setattr(renderer, "modern_oilfield_report_profile", lambda: replace(visual, palette=palette))
    sample = renderer.FrozenCuttingsSample("sample", 1.0, 9.0, (renderer.FrozenCuttingsComponent("sand", 100.0),), lba_group=1, lba_intensity=3)
    painter = MagicMock()
    patterns = []
    monkeypatch.setattr(renderer, "masterlog_lithology_brush", lambda _painter, color, pattern: patterns.append((color, pattern)))
    renderer.paint_cuttings_track(painter, QRectF(0, 0, 90, 100), (sample,), (0, 10), {"sand": SimpleNamespace(color="#abcdef", pattern_key="sandstone_bricks")})
    assert patterns == [("#abcdef", "sandstone_bricks")]
    pen_colors = {call.args[0].color().name() for call in painter.setPen.call_args_list if isinstance(call.args[0], QPen)}
    assert {palette.border_strong, palette.text_secondary} <= pen_colors
    painter.reset_mock()
    symbols = []
    monkeypatch.setattr(renderer, "paint_lba_intensity_symbol", lambda *args: symbols.append(args))
    renderer.paint_lba_track(painter, QRectF(0, 0, 90, 100), (sample,), (0, 10))
    pen_colors = {call.args[0].color().name() for call in painter.setPen.call_args_list if isinstance(call.args[0], QPen)}
    assert {palette.border_strong, palette.border} <= pen_colors
    assert any(isinstance(call.args[0], QColor) and call.args[0].name() == palette.text for call in painter.setPen.call_args_list)
    assert symbols[0][4].name() == renderer.lba_standard_group(1).display_color
    assert sample.components[0].percentage == 100.0 and sample.lba_intensity == 3
