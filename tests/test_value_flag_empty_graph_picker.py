from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QMenu

import geoworkbench.tablet.tablet_view as tablet_module

from geoworkbench.domain.models import Dataset, DatasetIndex, DatasetKind, DepthDomain, IndexRole, IndexType
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("mode", ["depth", "time", "signed"])
def test_empty_graph_menu_selects_real_sample_and_saves_value(qapp, monkeypatch, language, mode):
    depth = np.array([-100.0, -99.0, -98.0] if mode == "signed" else
                     [100.0, 100.0, 101.0] if mode == "time" else [100.0, 101.0, 102.0])
    dataset = Dataset("flags", "Flags", DatasetKind.GTI,
                      DepthDomain.TVDSS if mode == "signed" else DepthDomain.MD, depth)
    if mode == "time":
        dataset.add_index(DatasetIndex("time", "TIME", IndexType.RELATIVE_TIME,
                                      IndexRole.TIME, "s", np.array([0.0, 60.0, 120.0])))
    for mnemonic, values in (("TG", [10.0, 20.0, 30.0]), ("C1", [2.0, 3.0, 4.0]),
                             ("GAP", [np.nan] * 3), ("FOREIGN", [7.0] * 3)):
        dataset.upsert_curve(mnemonic, np.array(values), unit="%")
    layout = TabletLayout([TrackDefinition("gas", "Gas", TrackKind.GAS,
                                          curve_mnemonics=["TG", "C1", "GAP"])],
                          vertical_index_id="time" if mode == "time" else None)
    session = ProjectSession()
    session.add_dataset(dataset)
    session.tablet_layouts[dataset.dataset_id] = layout
    view = TabletView(language=language)
    view.set_layout_and_dataset(layout, dataset)
    controller = DepthAnnotationController(session)
    saved = []

    def save(payload):
        saved.append(controller.add_curve_value(**{
            key: payload[key] for key in ("track_id", "depth", "axis_value", "axis_id",
                                         "mnemonic", "value", "unit", "x_fraction")
        }))

    view.curve_value_save_requested.connect(save)
    monkeypatch.setattr(view, "hit_test_curve", lambda *args, **kwargs: None)
    label = view._localizer.text("annotations.save_curve_value_action")
    class ScriptedMenu(QMenu):
        def exec(self, position):
            return next(action for action in self.actions() if action.text() == label)

    monkeypatch.setattr(tablet_module, "QMenu", ScriptedMenu)

    def choose(parent, title, prompt, items, current, editable):
        assert title == label
        assert prompt == view._localizer.text("inspector.curve")
        assert len(items) == 2
        assert items[0].startswith("TG:") and items[1].startswith("C1:")
        assert current == 0 and editable is False
        return items[1], True

    monkeypatch.setattr(tablet_module, "QInputDialog", SimpleNamespace(getItem=choose))
    before = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    clicked_y = 64.0 if mode == "time" else -99.6 if mode == "signed" else 100.4
    try:
        assert view._curve_value_payload("gas", 0.98, clicked_y, mnemonic="FOREIGN") is None
        view.show_track_context_menu("gas", QPoint(), local_x=0.98, local_y=clicked_y)
        assert len(saved) == 1
        flag = saved[0]
        row = 1 if mode == "time" else 0
        assert flag.parameter_mnemonic == "C1"
        assert flag.parameter_value == [2.0, 3.0, 4.0][row]
        assert flag.depth == depth[row]
        assert flag.axis_value == (60.0 if mode == "time" else depth[row])
        assert flag.visible and flag.print_enabled
        for key, curve in dataset.curves.items():
            np.testing.assert_array_equal(curve.values, before[key])
        np.testing.assert_array_equal(dataset.depth, depth)
    finally:
        view.clear()
        view.close()
        view.deleteLater()
        qapp.processEvents()


@pytest.mark.parametrize("cancel_menu", [False, True])
def test_empty_graph_picker_cancel_does_not_save_or_open_editor(qapp, monkeypatch, cancel_menu):
    dataset = Dataset("flags", "Flags", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 101.0]))
    dataset.upsert_curve("TG", np.array([10.0, 20.0]), unit="%")
    session = ProjectSession()
    session.add_dataset(dataset)
    view = TabletView()
    view.set_layout_and_dataset(TabletLayout([
        TrackDefinition("gas", "Gas", TrackKind.CURVE, curve_mnemonics=["TG"]),
    ]), dataset)
    saved, edited = [], []
    view.curve_value_save_requested.connect(saved.append)
    view.track_full_edit_requested.connect(edited.append)
    monkeypatch.setattr(view, "hit_test_curve", lambda *args, **kwargs: None)
    label = view._localizer.text("annotations.save_curve_value_action")
    class ScriptedMenu(QMenu):
        def exec(self, point):
            if cancel_menu:
                return None
            return next(action for action in self.actions() if action.text() == label)

    monkeypatch.setattr(tablet_module, "QMenu", ScriptedMenu)
    monkeypatch.setattr(tablet_module, "QInputDialog",
                        SimpleNamespace(getItem=lambda *args: ("", False)))
    before = deepcopy(session.current_well.canvas_objects)
    try:
        view.show_track_context_menu("gas", QPoint(), local_x=0.98, local_y=100.4)
        assert saved == [] and edited == []
        assert session.current_well.canvas_objects == before
        np.testing.assert_array_equal(dataset.curve_by_mnemonic("TG").values, [10.0, 20.0])
        assert view._curve_value_choices("gas", float("nan"), 100.0) == ()
        assert view._curve_value_choices("gas", 0.5, float("inf")) == ()
    finally:
        view.clear()
        view.close()
        view.deleteLater()
        qapp.processEvents()
