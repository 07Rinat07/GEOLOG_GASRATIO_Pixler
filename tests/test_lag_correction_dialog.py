import numpy as np
from PySide6.QtWidgets import QDialogButtonBox, QScrollArea, QTableWidget

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    Project,
    Well,
)
from geoworkbench.project.lag_correction_controller import LagCorrectionProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.lag_correction_dialog import LagCorrectionDialog


def _session() -> ProjectSession:
    dataset = Dataset(
        "source",
        "Source",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([10.0, 20.0, 30.0]),
    )
    dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 10.0, 20.0]),
        )
    )
    dataset.curves["gas"] = CurveData(
        CurveMetadata("gas", "TGAS", "TGAS", "%", None, dataset.dataset_id),
        np.array([1.0, 2.0, 3.0]),
    )
    well = Well("well", "Well", datasets={dataset.dataset_id: dataset})
    return ProjectSession(
        Project("project", "Project", wells={well.well_id: well}),
        well.well_id,
        dataset.dataset_id,
    )


def test_lag_correction_dialog_fits_work_area_with_sticky_close(qapp) -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    dialog = LagCorrectionDialog(
        dataset,
        LagCorrectionProjectController(session),
        language=AppLanguage.EN,
    )
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()

        scroll = dialog.findChild(QScrollArea, "lag-correction-body-scroll")
        buttons = dialog.findChild(QDialogButtonBox)
        table = dialog.findChild(QTableWidget, "lag-correction-preview")
        assert scroll is not None
        assert buttons is not None
        assert table is not None
        assert scroll.widget() is not None
        assert scroll.widget().isAncestorOf(table)
        assert not scroll.isAncestorOf(buttons)
        assert buttons.button(QDialogButtonBox.StandardButton.Close).text() == "Close"
        assert dialog.curve_list.count() == 1
        assert dialog.time_selector.count() == 2
    finally:
        dialog.close()
