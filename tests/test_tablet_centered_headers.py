from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from geoworkbench.forms.catalog import visible_factory_forms
from geoworkbench.forms.codec import form_from_dict, form_to_dict
from geoworkbench.forms.models import FormAxisKind, FormColumn, FormDocument, FormTrack
from geoworkbench.tablet.layout_codec import layout_from_dict, layout_to_dict
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.ui.oriented_text_label import OrientedTextLabel


@pytest.mark.parametrize("orientation", ("horizontal", "vertical_bottom_to_top", "vertical_top_to_bottom"))
def test_old_tablet_bottom_title_migrates_once(orientation):
    layout = TabletLayout([
        TrackDefinition("strat", "Стратиграфия", TrackKind.STRATIGRAPHY,
                        title_orientation=orientation, title_position="bottom", width=100),
    ])
    payload = layout_to_dict(layout)
    payload["version"] = 25
    restored = layout_from_dict(payload)
    track = restored.tracks[0]
    assert track.title_position == "center"
    assert track.title_orientation == orientation
    assert track.width == 100
    assert payload["tracks"][0]["title_position"] == "bottom"
    track.title_position = "bottom"
    assert layout_from_dict(layout_to_dict(restored)).tracks[0].title_position == "bottom"


def test_saved_form_recenter_both_levels_and_keep_new_explicit_override():
    form = FormDocument.create("Saved form", FormAxisKind.DEPTH)
    form.add_column(FormColumn.create(
        "Depth", title_position="bottom", tracks=[
            FormTrack.create("Depth", TrackKind.DEPTH, title_position="bottom"),
        ],
    ))
    payload = form_to_dict(form)
    payload["schema_version"] = 18
    restored = form_from_dict(payload)
    column = restored.columns[0]
    assert column.title_position == column.tracks[0].title_position == "center"
    column.title_position = "bottom"
    column.tracks[0].title_position = "top"
    reopened = form_from_dict(form_to_dict(restored))
    assert reopened.columns[0].title_position == "bottom"
    assert reopened.columns[0].tracks[0].title_position == "top"


@pytest.mark.parametrize("language", ("ru", "kk", "en"))
def test_all_factory_caption_defaults_center(language):
    forms = visible_factory_forms(None, language)
    assert forms
    for form in forms:
        for column in form.columns:
            assert column.title_position == "center"
            for track in column.tracks:
                assert track.title_position == "center"


@pytest.mark.parametrize("orientation", ("horizontal", "vertical_bottom_to_top", "vertical_top_to_bottom"))
def test_centered_caption_alignment_in_tall_header(qapp, orientation):
    label = OrientedTextLabel("Стратиграфия", orientation=orientation)
    try:
        label.resize(100, 300)
        assert label.vertical_position == "center"
        assert label.alignment() == Qt.AlignmentFlag.AlignCenter
    finally:
        label.close()
