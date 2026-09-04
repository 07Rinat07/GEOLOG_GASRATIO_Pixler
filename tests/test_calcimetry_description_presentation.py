from __future__ import annotations

import numpy as np
import pyqtgraph as pg

from geoworkbench.domain.models import CuttingsSample, Dataset, DatasetKind, DepthDomain
from geoworkbench.forms.a4_factory_templates import a4_factory_templates
from geoworkbench.forms.apply import FormApplyEngine
from geoworkbench.forms.codec import form_from_dict, form_to_dict
from geoworkbench.forms.from_tablet import form_from_tablet_layout
from geoworkbench.forms.models import FormAxisKind, FormColumn, FormDocument, FormTrack
from geoworkbench.forms.templates import factory_templates
from geoworkbench.tablet.layout_codec import layout_from_dict, layout_to_dict
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView
from geoworkbench.ui.tablet_track_editor_dialog import TabletTrackEditorDialog


def test_calcimetry_orientation_and_description_borders_round_trip() -> None:
    layout = TabletLayout(
        [
            TrackDefinition(
                "calc",
                "Calcimetry",
                TrackKind.CALCIMETRY,
                calcimetry_label_orientation="vertical_top_to_bottom",
            ),
            TrackDefinition(
                "description",
                "Description",
                TrackKind.TEXT,
                show_description_borders=False,
            ),
        ]
    )

    restored = layout_from_dict(layout_to_dict(layout))

    assert (
        restored.track_by_id("calc").calcimetry_label_orientation
        == "vertical_top_to_bottom"
    )
    assert restored.track_by_id("description").show_description_borders is False

    legacy = layout_to_dict(layout)
    legacy["version"] = 23
    for track in legacy["tracks"]:
        track.pop("calcimetry_label_orientation")
        track.pop("show_description_borders")
    migrated = layout_from_dict(legacy)
    assert (
        migrated.track_by_id("calc").calcimetry_label_orientation
        == "vertical_top_to_bottom"
    )
    assert migrated.track_by_id("description").show_description_borders is True


def test_calcimetry_and_description_settings_survive_forms() -> None:
    form = FormDocument.create("Presentation", FormAxisKind.DEPTH)
    form.add_column(
        FormColumn.create(
            "Calc",
            tracks=[
                FormTrack.create(
                    "Calc",
                    TrackKind.CALCIMETRY,
                    calcimetry_label_orientation="vertical_bottom_to_top",
                )
            ],
        )
    )
    form.add_column(
        FormColumn.create(
            "Description",
            tracks=[
                FormTrack.create(
                    "Description",
                    TrackKind.TEXT,
                    show_description_borders=False,
                )
            ],
        )
    )

    restored = form_from_dict(form_to_dict(form))
    assert (
        restored.columns[0].tracks[0].calcimetry_label_orientation
        == "vertical_bottom_to_top"
    )
    assert restored.columns[1].tracks[0].show_description_borders is False

    dataset = Dataset(
        "presentation",
        "Presentation",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    applied = FormApplyEngine().build_layout(restored, dataset).layout
    recreated = form_from_tablet_layout(applied, dataset, "Recreated")
    assert recreated.columns[1].tracks[0].show_description_borders is False


def test_all_factory_calcimetry_tracks_include_insoluble_residue() -> None:
    forms = {
        **factory_templates("ru"),
        **a4_factory_templates("ru"),
    }
    tracks = [
        track
        for form in forms.values()
        for column in form.columns
        for track in column.tracks
        if track.kind is TrackKind.CALCIMETRY
    ]

    assert tracks
    assert all(
        "INSOLUBLE_RESIDUE"
        in {binding.canonical_parameter_id for binding in track.bindings}
        for track in tracks
    )


def test_calcimetry_track_editor_changes_label_direction(qapp) -> None:
    track = TrackDefinition(
        "calc",
        "Calcimetry",
        TrackKind.CALCIMETRY,
        calcimetry_label_orientation="horizontal",
    )
    dialog = TabletTrackEditorDialog(track, language="en")

    assert not dialog.calcimetry_label_orientation_input.isHidden()
    dialog.calcimetry_label_orientation_input.setCurrentIndex(
        dialog.calcimetry_label_orientation_input.findData(
            "vertical_top_to_bottom"
        )
    )

    assert (
        dialog._track_from_controls().calcimetry_label_orientation
        == "vertical_top_to_bottom"
    )
    dialog.close()


def test_tablet_rotates_calcimetry_interval_label(qapp) -> None:
    dataset = Dataset(
        "calc-orientation",
        "Calc orientation",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 105.0, 110.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "calc",
                    "Calcimetry",
                    TrackKind.CALCIMETRY,
                    calcimetry_label_orientation="vertical_top_to_bottom",
                )
            ]
        )
    )
    view.set_cuttings(
        [
            CuttingsSample(
                "sample",
                100.0,
                110.0,
                calcite_percent=55.0,
                dolomite_percent=35.0,
            )
        ]
    )
    view.set_dataset(dataset)

    items = view._rendered["calc"].analysis_items
    assert items is not None
    labels = [item for item in items["sample"] if isinstance(item, pg.TextItem)]
    assert len(labels) == 1
    assert labels[0].angle == 90.0
    assert "Н.О." in labels[0].textItem.toPlainText()
    view.close()