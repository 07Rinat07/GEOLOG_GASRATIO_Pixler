from __future__ import annotations

import pytest

from geoworkbench.tablet.models import TrackDefinition, TrackKind
from geoworkbench.tablet.vertical_ruler import (
    VerticalRulerMode,
    VerticalRulerTrackSettings,
)
from geoworkbench.ui.tablet_track_editor_dialog import TabletTrackEditorDialog


def _gas_track(
    settings: VerticalRulerTrackSettings | None = None,
) -> TrackDefinition:
    return TrackDefinition(
        track_id="gas",
        title="Газы",
        kind=TrackKind.GAS,
        curve_mnemonics=["C1", "C2"],
        vertical_ruler=settings or VerticalRulerTrackSettings(),
    )


def test_editor_loads_and_returns_per_track_ruler_settings(qapp) -> None:
    source = VerticalRulerTrackSettings(
        mode=VerticalRulerMode.TICKS_ONLY,
        label_every_major=2,
        major_tick_every=3,
        minor_tick_every=4,
    )
    dialog = TabletTrackEditorDialog(_gas_track(source), language="ru")

    assert dialog.vertical_ruler_mode_input.currentData() == source.mode.value
    assert dialog.vertical_ruler_label_every_input.value() == 2
    assert dialog.vertical_ruler_major_tick_every_input.value() == 3
    assert dialog.vertical_ruler_minor_tick_every_input.value() == 4

    dialog.vertical_ruler_mode_input.setCurrentIndex(
        dialog.vertical_ruler_mode_input.findData(
            VerticalRulerMode.LABELS_AND_TICKS
        )
    )
    dialog.vertical_ruler_label_every_input.setValue(5)
    dialog.vertical_ruler_major_tick_every_input.setValue(2)
    dialog.vertical_ruler_minor_tick_every_input.setValue(6)
    candidate = dialog._track_from_controls()

    assert candidate.vertical_ruler == VerticalRulerTrackSettings(
        mode=VerticalRulerMode.LABELS_AND_TICKS,
        label_every_major=5,
        major_tick_every=2,
        minor_tick_every=6,
    )
    dialog.close()


def test_off_and_ticks_only_modes_disable_only_irrelevant_controls(qapp) -> None:
    dialog = TabletTrackEditorDialog(_gas_track(), language="en")

    dialog.vertical_ruler_mode_input.setCurrentIndex(
        dialog.vertical_ruler_mode_input.findData(VerticalRulerMode.OFF.value)
    )
    assert not dialog.vertical_ruler_label_every_input.isEnabled()
    assert not dialog.vertical_ruler_major_tick_every_input.isEnabled()
    assert not dialog.vertical_ruler_minor_tick_every_input.isEnabled()

    dialog.vertical_ruler_mode_input.setCurrentIndex(
        dialog.vertical_ruler_mode_input.findData(
            VerticalRulerMode.TICKS_ONLY
        )
    )
    assert not dialog.vertical_ruler_label_every_input.isEnabled()
    assert dialog.vertical_ruler_major_tick_every_input.isEnabled()
    assert dialog.vertical_ruler_minor_tick_every_input.isEnabled()
    dialog.close()


def test_non_graphical_track_cannot_enable_inner_ruler_controls(qapp) -> None:
    dialog = TabletTrackEditorDialog(
        TrackDefinition(
            track_id="lithology",
            title="Литология",
            kind=TrackKind.LITHOLOGY,
        ),
        language="ru",
    )

    assert not dialog.vertical_ruler_group.isEnabled()
    dialog.close()


@pytest.mark.parametrize(
    ("language", "title", "labels_text", "off_text"),
    [
        ("ru", "Внутренняя вертикальная шкала", "Цифры и риски", "Выключено"),
        ("kk", "Ішкі тік шкала", "Сандар мен белгілер", "Өшірулі"),
        ("en", "Inner vertical ruler", "Labels and ticks", "Off"),
    ],
)
def test_editor_exposes_ruler_controls_in_three_languages(
    qapp, language: str, title: str, labels_text: str, off_text: str
) -> None:
    dialog = TabletTrackEditorDialog(_gas_track(), language=language)

    assert dialog.vertical_ruler_group.title() == title
    labels_index = dialog.vertical_ruler_mode_input.findData(
        VerticalRulerMode.LABELS_AND_TICKS
    )
    off_index = dialog.vertical_ruler_mode_input.findData(
        VerticalRulerMode.OFF
    )
    assert dialog.vertical_ruler_mode_input.itemText(labels_index) == labels_text
    assert dialog.vertical_ruler_mode_input.itemText(off_index) == off_text
    dialog.close()
