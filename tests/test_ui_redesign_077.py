from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.forms.from_tablet import form_from_tablet_layout
from geoworkbench.forms.models import FormAxisKind, FormDocument
from geoworkbench.forms.repository import FormRepository
from geoworkbench.tablet.models import (
    CurveDisplaySettings,
    CurveStyle,
    TabletLayout,
    TrackDefinition,
    TrackKind,
    XScale,
)
from geoworkbench.ui.constructor_dialog import UniversalConstructorDialog
from geoworkbench.ui.form_manager_dialog import FormManagerDialog
from geoworkbench.ui.main_window import MainWindow


def test_repository_separates_depth_and_time_forms(tmp_path) -> None:
    repository = FormRepository(tmp_path / "forms")
    depth = FormDocument.create("Depth", FormAxisKind.DEPTH)
    time = FormDocument.create("Time", FormAxisKind.TIME)

    depth_path = repository.save(depth)
    time_path = repository.save(time)

    assert depth_path.parent.name == "depth"
    assert time_path.parent.name == "time"
    assert {item.name for item in repository.list_forms()} == {"Depth", "Time"}


def test_live_tablet_layout_converts_to_editable_user_form() -> None:
    dataset = Dataset(
        "dataset-ui-form",
        "Well A",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 100.5, 101.0]),
    )
    dataset.upsert_curve("ROP", np.array([10.0, 20.0, 30.0]), unit="m/h")
    track = TrackDefinition(
        "track-rop",
        "Скорость бурения",
        TrackKind.CURVE,
        curve_mnemonics=["ROP"],
        width=310,
        locked=True,
        grid_x=True,
        grid_y=False,
        title_orientation="vertical_bottom_to_top",
        title_position="bottom",
        curve_styles={"ROP": CurveStyle("#dc2626", 2.0)},
        curve_display={
            "ROP": CurveDisplaySettings("ROP, м/ч", XScale.LINEAR, 0.0, 150.0)
        },
    )
    layout = TabletLayout([track], vertical_index_id=dataset.active_index.index_id)

    form = form_from_tablet_layout(layout, dataset, "Рабочая форма")

    assert form.axis_kind is FormAxisKind.DEPTH
    assert form.read_only is False
    assert form.columns[0].width == 310
    assert form.columns[0].tracks[0].locked is False
    assert form.columns[0].tracks[0].title_orientation == "vertical_bottom_to_top"
    binding = form.columns[0].tracks[0].bindings[0]
    assert binding.source_mnemonic == "ROP"
    assert binding.display_name == "ROP, м/ч"
    assert binding.x_min == 0.0
    assert binding.x_max == 150.0


def test_form_manager_has_axis_grouped_library(qapp, tmp_path) -> None:
    repository = FormRepository(tmp_path / "forms")
    repository.save(FormDocument.create("User depth", FormAxisKind.DEPTH))
    repository.save(FormDocument.create("User time", FormAxisKind.TIME))

    dialog = FormManagerDialog(repository, language="ru")

    titles = [
        dialog.tree_widget.topLevelItem(index).text(0)
        for index in range(dialog.tree_widget.topLevelItemCount())
    ]
    assert any("Пользовательские формы — глубина" in title for title in titles)
    assert any("Пользовательские формы — время" in title for title in titles)


def test_f4_edit_mode_toggles_secondary_toolbar(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    window = MainWindow()
    window.show()
    qapp.processEvents()

    assert window.form_edit_toolbar.isVisible() is False
    window.tablet_edit_mode_action.setChecked(True)
    qapp.processEvents()

    assert window.form_edit_toolbar.isVisible() is True
    assert window.tablet_view.form_edit_mode is True
    assert window.form_manager_button.defaultAction() is window.form_manager_action
    assert window.form_manager_button.menu() is None


def test_constructor_shows_ready_kazgeology_preset(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    window = MainWindow()
    dialog = UniversalConstructorDialog(
        window.masterlog_template_controller,
        language=window.language,
    )

    preset_ids = {
        dialog.preset_list.item(row).data(0x0100)
        for row in range(dialog.preset_list.count())
    }
    assert "kazgeology_reference_blank" in preset_ids
    assert dialog.navigation.count() == 4
