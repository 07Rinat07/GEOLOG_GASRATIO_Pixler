import numpy as np

from geoworkbench.domain.models import (
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.time_to_depth_dialog import TimeToDepthDialog


def _dataset() -> Dataset:
    return Dataset(
        "time-depth-dialog",
        "Time log",
        DatasetKind.USER,
        DepthDomain.TIME,
        np.array([0.0, 1.0, 2.0]),
        indexes={
            "time": DatasetIndex(
                "time",
                "TIME",
                IndexType.RELATIVE_TIME,
                IndexRole.TIME,
                "s",
                np.array([0.0, 1.0, 2.0]),
            ),
            "depth": DatasetIndex(
                "depth",
                "DEPTH",
                IndexType.MD,
                IndexRole.DEPTH,
                "m",
                np.array([100.0, 100.1, 100.2]),
            ),
        },
        active_index_id="time",
    )


def test_time_to_depth_dialog_fits_current_work_area(qapp) -> None:
    dialog = TimeToDepthDialog(_dataset(), language=AppLanguage.EN)
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()
        assert dialog.depth_index.count() == 1
        assert dialog.time_index.count() == 2
    finally:
        dialog.close()
