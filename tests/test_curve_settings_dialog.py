import numpy as np
from PySide6.QtWidgets import QDialogButtonBox, QScrollArea

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.models import TrackDefinition, TrackKind
from geoworkbench.ui.curve_settings_dialog import CurveSettingsDialog


def _dataset_and_track() -> tuple[Dataset, TrackDefinition]:
    dataset = Dataset(
        "adaptive-curves",
        "Adaptive curves",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]),
    )
    metadata = CurveMetadata(
        "curve-rop",
        "ROP",
        "ROP",
        "m/h",
        "Rate of penetration",
        dataset.dataset_id,
    )
    dataset.curves[metadata.curve_id] = CurveData(
        metadata,
        np.array([10.0, 20.0, 30.0]),
    )
    track = TrackDefinition("track-rop", "ROP", TrackKind.CURVE, ["ROP"])
    return dataset, track


def test_curve_settings_dialog_fits_current_work_area(qapp) -> None:
    dataset, track = _dataset_and_track()
    dialog = CurveSettingsDialog(track, dataset, language=AppLanguage.EN)
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()
        assert dialog.curves.currentRow() == 0
        assert dialog.mnemonic_label.text() == "ROP"
        scroll = dialog.findChild(QScrollArea, "curve-settings-editor-scroll")
        buttons = dialog.findChild(QDialogButtonBox)
        assert scroll is not None
        assert buttons is not None
        assert not scroll.isAncestorOf(buttons)
    finally:
        dialog.close()
