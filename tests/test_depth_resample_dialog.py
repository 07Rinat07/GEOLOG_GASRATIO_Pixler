import numpy as np
from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.depth_axis_controller import DepthAxisController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.depth_resample_dialog import DepthResampleDialog


def make_controller() -> DepthAxisController:
    session = ProjectSession()
    session.add_dataset(
        Dataset(
            "dataset",
            "LAS",
            DatasetKind.GTI,
            DepthDomain.MD,
            np.array([100.0, 101.0, 102.0]),
        )
    )
    return DepthAxisController(session)


def test_dialog_previews_target_grid_and_disables_invalid_plan(qapp) -> None:
    dialog = DepthResampleDialog(make_controller(), language=AppLanguage.EN)
    ok_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)

    dialog.step_input.setValue(0.5)
    assert dialog.plan is not None
    assert dialog.plan.target_sample_count == 5
    assert "target samples: 5" in dialog.preview.text()
    assert ok_button.isEnabled()

    dialog.stop_input.setValue(99.0)
    assert dialog.plan is None
    assert "invalid" in dialog.preview.text().lower()
    assert not ok_button.isEnabled()
    dialog.close()
