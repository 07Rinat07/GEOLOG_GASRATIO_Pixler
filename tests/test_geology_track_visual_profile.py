from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPen

from geoworkbench.printing import geology_track_rendering as renderer
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.printing.hydrocarbon_interpretation_geology import interpretation_geology_snapshot
from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    InterpretationGeologyTrackSettings, GeologyTrackVisibility,
    resolve_geology_track_kinds, forced_empty_geology_tracks,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_legend import build_interpretation_geology_legend
from geoworkbench.printing.lba_visuals import UNKNOWN_LBA_STYLE
from geoworkbench.services.localization import AppLanguage
from test_report_geology_snapshot import _session
from geoworkbench.services.lba_observations import has_recorded_lba


@pytest.mark.parametrize(("sample", "expected"), (
    (SimpleNamespace(lba_intensity=0), True),
    (SimpleNamespace(lba_group=0), True),
    (SimpleNamespace(lba_description="Legacy observation"), True),
    (SimpleNamespace(lba_description="   "), False),
    (SimpleNamespace(), False),
))
def test_lba_presence_preserves_zero_and_legacy_models(sample, expected):
    assert has_recorded_lba(sample) is expected


@pytest.mark.parametrize("field", (
    "lba_cut_speed", "lba_cut_color", "lba_residue_type",
    "lba_residue_color", "lba_odour", "lba_stain",
))
@pytest.mark.parametrize("value", ("Saved detail <original>", None, "", "   "))
def test_partial_lba_survives_snapshot_tracks_legend_and_painter(qapp, monkeypatch, field, value):
    session = _session()
    sample = session.current_well.cuttings[0]
    session.current_well.cuttings[:] = [sample]
    sample.components.clear()
    for name in ("lba_group", "lba_type_id", "lba_intensity", "lba_color", "lba_distribution", "lba_cut", "lba_description"):
        setattr(sample, name, None)
    setattr(sample, field, value)
    before = repr(sample)
    geology = interpretation_geology_snapshot(session)
    recorded = bool(value and value.strip())
    assert (geology is not None) is recorded
    assert resolve_geology_track_kinds(geology, 1002.0, 1010.0, InterpretationGeologyTrackSettings()) == (("lba",) if recorded else ())
    show = InterpretationGeologyTrackSettings(lba=GeologyTrackVisibility.SHOW)
    assert forced_empty_geology_tracks(geology, 1002.0, 1010.0, show) == (() if recorded else ("lba",))
    for language in AppLanguage:
        legend = build_interpretation_geology_legend(geology, 1002.0, 1010.0, language)
        assert legend.empty is (not recorded)
        if recorded:
            assert [(item.kind, item.key, item.intensity) for item in legend.items] == [("lba-type", UNKNOWN_LBA_STYLE.type_id, None)]
    symbols = []
    monkeypatch.setattr(renderer, "paint_lba_intensity_symbol", lambda *args: symbols.append(args))
    painter = MagicMock()
    renderer.paint_lba_track(painter, QRectF(0, 0, 90, 100), geology.samples if geology else (), (1002.0, 1010.0))
    assert len(symbols) == int(recorded)
    if recorded:
        assert getattr(geology.samples[0], field) == value
        assert symbols[0][-1] is None
        assert symbols[0][-2].name() == UNKNOWN_LBA_STYLE.color
        sample_texts = [call.args[-1] for call in painter.drawText.call_args_list]
        assert "?" in sample_texts
    assert repr(sample) == before


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
