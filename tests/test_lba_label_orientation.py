from __future__ import annotations

import numpy as np
import pyqtgraph as pg
import pytest
from PySide6.QtCore import QPointF

from geoworkbench.domain.models import (
    CuttingsSample,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.forms.apply import FormApplyEngine
from geoworkbench.forms.catalog import visible_factory_forms
from geoworkbench.forms.codec import form_from_dict, form_to_dict
from geoworkbench.forms.from_tablet import form_from_tablet_layout
from geoworkbench.forms.models import FormAxisKind, FormColumn, FormDocument, FormTrack
from geoworkbench.tablet.layout_codec import layout_from_dict, layout_to_dict
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView
from geoworkbench.ui.tablet_track_editor_dialog import TabletTrackEditorDialog


def _lba_track(
    orientation: str = "vertical_bottom_to_top",
) -> TrackDefinition:
    return TrackDefinition(
        "lba",
        "ЛБА",
        TrackKind.LBA,
        width=180,
        lba_label_orientation=orientation,
    )


def test_lba_label_orientation_defaults_to_bottom_up_and_is_validated() -> None:
    track = TrackDefinition("lba", "ЛБА", TrackKind.LBA, width=180)

    assert track.lba_label_orientation == "vertical_bottom_to_top"
    with pytest.raises(ValueError, match="направление текста"):
        _lba_track("diagonal")


def test_lba_label_orientation_round_trip_and_v22_migration() -> None:
    source = TabletLayout([_lba_track("horizontal")])

    restored = layout_from_dict(layout_to_dict(source))

    assert restored.track_by_id("lba").lba_label_orientation == "horizontal"

    legacy = layout_to_dict(source)
    legacy["version"] = 22
    legacy["tracks"][0].pop("lba_label_orientation")
    migrated = layout_from_dict(legacy)
    assert (
        migrated.track_by_id("lba").lba_label_orientation
        == "vertical_bottom_to_top"
    )


def test_lba_label_orientation_round_trips_through_forms_and_v14_migration() -> None:
    form = FormDocument.create("LBA form", FormAxisKind.DEPTH)
    form.add_column(
        FormColumn.create(
            "LBA",
            tracks=[
                FormTrack.create(
                    "LBA",
                    TrackKind.LBA,
                    lba_label_orientation="horizontal",
                )
            ],
        )
    )

    restored = form_from_dict(form_to_dict(form))
    assert restored.columns[0].tracks[0].lba_label_orientation == "horizontal"

    legacy = form_to_dict(form)
    legacy["schema_version"] = 14
    legacy["columns"][0]["tracks"][0].pop("lba_label_orientation")
    migrated = form_from_dict(legacy)
    assert (
        migrated.columns[0].tracks[0].lba_label_orientation
        == "vertical_bottom_to_top"
    )


def test_visible_a4_factory_lba_forms_use_bottom_up_colour_and_bitumen_labels() -> None:
    lba_tracks = [
        track
        for form in visible_factory_forms(None, "ru")
        for column in form.columns
        for track in column.tracks
        if track.kind is TrackKind.LBA
    ]

    assert lba_tracks
    assert all(
        track.lba_label_orientation == "vertical_bottom_to_top"
        for track in lba_tracks
    )


def test_lba_label_orientation_survives_form_apply_and_tablet_form_creation() -> None:
    dataset = Dataset(
        "lba-form",
        "LBA form",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    form = FormDocument.create("LBA", FormAxisKind.DEPTH)
    form.add_column(
        FormColumn.create(
            "LBA",
            width=180,
            tracks=[
                FormTrack.create(
                    "LBA",
                    TrackKind.LBA,
                    lba_label_orientation="vertical_top_to_bottom",
                )
            ],
        )
    )

    layout = FormApplyEngine().build_layout(form, dataset).layout
    assert layout.tracks[0].lba_label_orientation == "vertical_top_to_bottom"

    recreated = form_from_tablet_layout(layout, dataset, "Saved LBA")
    assert (
        recreated.columns[0].tracks[0].lba_label_orientation
        == "vertical_top_to_bottom"
    )


def test_lba_track_editor_changes_colour_and_bitumen_label_direction(qapp) -> None:
    dialog = TabletTrackEditorDialog(_lba_track(), language="ru")

    assert not dialog.lba_label_orientation_input.isHidden()
    assert (
        dialog.lba_label_orientation_input.currentData()
        == "vertical_bottom_to_top"
    )
    dialog.lba_label_orientation_input.setCurrentIndex(
        dialog.lba_label_orientation_input.findData("vertical_top_to_bottom")
    )

    candidate = dialog._track_from_controls()

    assert candidate.lba_label_orientation == "vertical_top_to_bottom"
    dialog.close()


def test_non_lba_track_hides_lba_label_direction_control(qapp) -> None:
    dialog = TabletTrackEditorDialog(
        TrackDefinition("curve", "Curve", TrackKind.CURVE),
        language="en",
    )

    assert dialog.lba_label_orientation_label.isHidden()
    assert dialog.lba_label_orientation_input.isHidden()
    dialog.close()


@pytest.mark.parametrize("orientation, angle", [
    ("vertical_bottom_to_top", 90.0),
    ("vertical_top_to_bottom", -90.0),
    ("horizontal", 0.0),
])
def test_tablet_rotates_only_lba_colour_and_bitumen_labels(qapp, orientation, angle) -> None:
    dataset = Dataset(
        "lba-orientation",
        "LBA orientation",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 105.0, 110.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout([_lba_track(orientation)])
    )
    view.set_cuttings(
        [
            CuttingsSample(
                "sample",
                100.0,
                110.0,
                lba_type_id="МСБ",
                lba_intensity=3,
                lba_color="ОЖ",
            )
        ]
    )
    view.set_dataset(dataset)

    items = view._rendered["lba"].analysis_items
    assert items is not None
    labels = {
        item.textItem.toPlainText(): item
        for item in items["sample"]
        if isinstance(item, pg.TextItem)
    }
    assert labels["3"].angle == 0
    assert labels["ОЖ"].angle == angle
    assert labels["МСБ"].angle == angle
    for code in ("ОЖ", "МСБ"):
        label = labels[code]
        label.updateTransform(force=True)
        delta = label.mapToScene(QPointF(1, 0)) - label.mapToScene(QPointF(0, 0))
        if orientation == "horizontal":
            assert delta.x() > 0 and abs(delta.y()) < 1e-6
        else:
            assert abs(delta.x()) < 1e-6
            assert (delta.y() < 0) == (orientation == "vertical_bottom_to_top")
    view.close()


@pytest.mark.parametrize("old_orientation, expected", [
    ("vertical_top_to_bottom", "vertical_bottom_to_top"),
    ("vertical_bottom_to_top", "vertical_bottom_to_top"),
    ("horizontal", "horizontal"),
])
def test_legacy_lba_orientation_migrates_once_in_layout_and_form(old_orientation, expected):
    layout = TabletLayout([_lba_track(old_orientation)])
    payload = layout_to_dict(layout)
    payload["version"] = 25
    restored = layout_from_dict(payload)
    assert restored.tracks[0].lba_label_orientation == expected
    restored.tracks[0].lba_label_orientation = "vertical_top_to_bottom"
    assert layout_from_dict(layout_to_dict(restored)).tracks[0].lba_label_orientation == "vertical_top_to_bottom"

    form = FormDocument.create("Legacy LBA", FormAxisKind.DEPTH)
    form.add_column(FormColumn.create("LBA", tracks=[
        FormTrack.create("LBA", TrackKind.LBA, lba_label_orientation=old_orientation),
    ]))
    raw = form_to_dict(form)
    raw["schema_version"] = 18
    reopened = form_from_dict(raw)
    track = reopened.columns[0].tracks[0]
    assert track.lba_label_orientation == expected
    track.lba_label_orientation = "vertical_top_to_bottom"
    assert form_from_dict(form_to_dict(reopened)).columns[0].tracks[0].lba_label_orientation == "vertical_top_to_bottom"


def test_new_lba_form_and_layout_default_to_bottom_up():
    form = FormDocument.create("LBA", FormAxisKind.DEPTH)
    track = FormTrack.create("LBA", TrackKind.LBA)
    form.add_column(FormColumn.create("LBA", tracks=[track]))
    assert track.lba_label_orientation == "vertical_bottom_to_top"
    assert form_from_dict(form_to_dict(form)).columns[0].tracks[0].lba_label_orientation == "vertical_bottom_to_top"
    assert _lba_track().lba_label_orientation == "vertical_bottom_to_top"


@pytest.mark.parametrize("language", ("ru", "kk", "en"))
def test_lba_defaults_to_bottom_up_in_all_visible_factory_forms(language):
    tracks = [
        track for form in visible_factory_forms(None, language)
        for column in form.columns for track in column.tracks if track.kind is TrackKind.LBA
    ]
    assert tracks and all(track.lba_label_orientation == "vertical_bottom_to_top" for track in tracks)
