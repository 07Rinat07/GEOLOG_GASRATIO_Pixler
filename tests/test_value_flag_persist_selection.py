from copy import deepcopy

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.annotation_schema import AnnotationKind
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.print_center_dialog import PrintCenterDialog


@pytest.mark.parametrize("suffix", [".json", ".geologpkg"])
def test_confirmed_value_selection_history_and_project_reopen(tmp_path, suffix):
    session = ProjectSession()
    dataset = Dataset("flags", "Flags", DatasetKind.GTI, DepthDomain.MD,
                      np.array([100.0, 101.0]))
    session.add_dataset(dataset)
    controller = DepthAnnotationController(session)
    first = controller.add_annotation(kind=AnnotationKind.VALUE, depth=100.0, text="First")
    second = controller.add_annotation(kind=AnnotationKind.VALUE, depth=101.0, text="Second")
    ids = (first.annotation_id, second.annotation_id)
    before = deepcopy(session.current_well.canvas_objects)
    controller.set_value_print_selection(ids, (first.annotation_id,))
    assert controller.get(first.annotation_id).print_enabled
    assert not controller.get(second.annotation_id).print_enabled
    assert all(record.visible for record in controller.available_annotations())
    controller.undo()
    assert session.current_well.canvas_objects == before
    controller.redo()
    project = ProjectController(session=session)
    target = tmp_path / ("flags" + suffix)
    project.save_project(target)
    reopened = ProjectController().open_project(target)
    reopened.current_well_id = session.current_well_id
    reopened.current_dataset_id = dataset.dataset_id
    restored = DepthAnnotationController(reopened)
    assert not restored.get(second.annotation_id).print_enabled
    np.testing.assert_array_equal(reopened.current_dataset.depth, dataset.depth)
    assert not reopened.dirty
    controller.set_value_print_selection(ids, ids)
    assert controller.get(second.annotation_id).print_enabled


def test_selection_validates_entire_batch_before_mutation():
    session = ProjectSession()
    session.add_dataset(Dataset("flags", "Flags", DatasetKind.GTI, DepthDomain.MD,
                                np.array([100.0, 101.0])))
    controller = DepthAnnotationController(session)
    flag = controller.add_annotation(kind=AnnotationKind.VALUE, depth=100.0, text="Flag")
    note = controller.add_annotation(kind=AnnotationKind.COMMENT, depth=100.0, text="Note")
    before = deepcopy(session.current_well.canvas_objects)
    with pytest.raises(ValueError, match="visible value"):
        controller.set_value_print_selection((flag.annotation_id, note.annotation_id), ())
    assert session.current_well.canvas_objects == before


@pytest.mark.parametrize("language", list(AppLanguage))
def test_print_selection_preserves_individual_choice_under_global_switch(qapp, language):
    dialog = PrintCenterDialog(language=language, printer_choices=(("Plotter", True),),
                               value_flag_options=(("a", "A"), ("b", "B")),
                               initial_value_flag_ids=("a",))
    try:
        assert dialog.job_settings().included_value_annotation_ids == ("a",)
        dialog.print_value_flags_check.setChecked(False)
        assert dialog.job_settings().included_value_annotation_ids == ()
        assert dialog.selected_value_annotation_ids() == ("a",)
        dialog.reject()
    finally:
        dialog.close()
