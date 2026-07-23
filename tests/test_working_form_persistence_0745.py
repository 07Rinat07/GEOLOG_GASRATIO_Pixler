from geoworkbench.forms import (
    FormAxisKind,
    FormColumn,
    FormDocument,
    FormTrack,
    ParameterBinding,
    form_from_dict,
    form_to_dict,
)
from geoworkbench.tablet.models import CurveStyle, TrackKind, XScale


def test_form_preserves_viewport_revision_and_header_colours() -> None:
    binding = ParameterBinding.create(
        "ROP",
        "Скорость бурения",
        source_mnemonic="ROP",
        style=CurveStyle("#ef4444", 2.0),
        x_scale=XScale.LINEAR,
        x_min=0.0,
        x_max=150.0,
        header_text_color="#1d4ed8",
        header_line_color="#f59e0b",
    )
    track = FormTrack.create(
        "Бурение",
        TrackKind.CURVE,
        bindings=[binding],
        grid_x=False,
        grid_y=True,
        grid_major_divisions=4,
        grid_minor_divisions=10,
        grid_alpha=0.35,
    )
    form = FormDocument.create("Рабочая форма", FormAxisKind.DEPTH)
    form.source_dataset_id = "depth-main"
    form.source_index_id = "depth-main:primary-index"
    form.visible_axis_top = 1000.0
    form.visible_axis_bottom = 1050.0
    form.revision = 7
    form.add_column(FormColumn.create("Бурение", width=410, tracks=[track]))

    restored = form_from_dict(form_to_dict(form))
    restored_binding = restored.columns[0].tracks[0].bindings[0]

    assert restored.revision == 7
    assert restored.source_dataset_id == "depth-main"
    assert restored.visible_axis_top == 1000.0
    assert restored.visible_axis_bottom == 1050.0
    assert restored.columns[0].width == 410
    assert restored.columns[0].tracks[0].grid_x is False
    assert restored_binding.header_text_color == "#1d4ed8"
    assert restored_binding.header_line_color == "#f59e0b"
