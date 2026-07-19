from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QApplication

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.forms.binding_editor import TrackBindingEditor
from geoworkbench.forms.editor import FormStructureEditor
from geoworkbench.forms.models import FormAxisKind, FormDocument
from geoworkbench.tablet.models import CurveLineStyle, TrackKind, XScale
from geoworkbench.ui.track_content_editor_dialog import TrackContentEditorDialog


def make_dataset() -> Dataset:
    dataset = Dataset(
        dataset_id="dataset",
        name="Well",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.array([1000.0, 1001.0]),
    )
    dataset.curves["tg"] = CurveData(
        CurveMetadata(
            curve_id="tg",
            original_mnemonic="TGAS",
            canonical_mnemonic="TG",
            unit="%",
            description="Total gas",
            source_dataset_id=dataset.dataset_id,
        ),
        np.array([1.0, 2.0]),
    )
    return dataset


def make_editor() -> tuple[FormStructureEditor, str]:
    form = FormDocument.create("Test", FormAxisKind.DEPTH)
    structure = FormStructureEditor(form)
    column = structure.add_column("Gas")
    track = structure.add_track(column.column_id, title="Gas", kind=TrackKind.GAS)
    return structure, track.track_id


def test_binding_editor_crud_order_and_style() -> None:
    structure, track_id = make_editor()
    editor = TrackBindingEditor(structure, track_id)
    tg = editor.add("TOTAL_GAS", "Total Gas", source_mnemonic="TGAS", unit="%")
    c1 = editor.add("C1", "Methane", source_mnemonic="C1", unit="ppm")

    editor.move(c1.binding_id, 0)
    updated = editor.update(
        tg.binding_id,
        display_name="TG",
        color="#ff0000",
        width=2.5,
        line_style=CurveLineStyle.DASH,
        x_scale=XScale.LOGARITHMIC,
        x_min=0.1,
        x_max=100.0,
    )

    assert editor.bindings[0].binding_id == c1.binding_id
    assert updated.display_name == "TG"
    assert updated.style.color == "#ff0000"
    assert updated.style.width == 2.5
    assert updated.style.line_style is CurveLineStyle.DASH
    assert updated.x_scale is XScale.LOGARITHMIC
    assert updated.x_min == 0.1
    assert structure.dirty is True

    removed = editor.remove(c1.binding_id)
    assert removed.binding_id == c1.binding_id
    assert [item.binding_id for item in editor.bindings] == [tg.binding_id]


def test_binding_editor_validates_logarithmic_range() -> None:
    structure, track_id = make_editor()
    editor = TrackBindingEditor(structure, track_id)
    binding = editor.add("TOTAL_GAS", "Total Gas")

    try:
        editor.update(
            binding.binding_id,
            x_scale=XScale.LOGARITHMIC,
            x_min=0.0,
            x_max=100.0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("zero logarithmic minimum must be rejected")


def test_track_content_dialog_can_add_las_curve(qapp: QApplication) -> None:
    structure, track_id = make_editor()
    dialog = TrackContentEditorDialog(
        structure,
        track_id,
        dataset=make_dataset(),
        language="en",
    )
    options = dialog._curve_options()
    assert options[0].mnemonic == "TGAS"
    assert options[0].canonical in {"TG", "TOTAL_GAS"}


def test_binding_settings_survive_json_and_apply(tmp_path) -> None:
    from geoworkbench.forms.apply import FormApplyEngine
    from geoworkbench.forms.repository import FormRepository

    structure, track_id = make_editor()
    editor = TrackBindingEditor(structure, track_id)
    editor.add(
        "TOTAL_GAS",
        "Total Gas",
        source_mnemonic="TGAS",
        unit="%",
        color="#ff0000",
        width=3.0,
        line_style=CurveLineStyle.DOT,
        x_scale=XScale.LOGARITHMIC,
        x_min=0.1,
        x_max=100.0,
    )
    repository = FormRepository(tmp_path / "forms")
    repository.save(structure.form)
    loaded = repository.load(structure.form.form_id)
    result = FormApplyEngine().build_layout(loaded, make_dataset())

    assert len(result.layout.tracks) == 1
    track = result.layout.tracks[0]
    assert track.curve_mnemonics == ["TGAS"]
    assert track.x_scale is XScale.LOGARITHMIC
    assert track.x_min == 0.1
    assert track.x_max == 100.0
    assert track.curve_styles["TGAS"].color == "#ff0000"
    assert track.curve_styles["TGAS"].width == 3.0
