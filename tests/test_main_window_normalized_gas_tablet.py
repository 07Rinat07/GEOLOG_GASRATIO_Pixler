from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    Project,
    Well,
)
from geoworkbench.project.interpretation_calculation_controller import (
    NormalizedGasCalculationMode,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.ui.main_window import MainWindow


def _add_curve(
    dataset: Dataset,
    mnemonic: str,
    values: np.ndarray,
    provenance: str,
) -> None:
    dataset.curves[mnemonic] = CurveData(
        CurveMetadata(
            mnemonic,
            mnemonic,
            mnemonic,
            "normalized gas units",
            mnemonic,
            dataset.dataset_id,
            provenance,
        ),
        np.asarray(values, dtype=np.float64),
    )


def _session() -> ProjectSession:
    depth = np.arange(1_000.0, 1_060.0)
    dataset = Dataset(
        "normalized-gas-tablet",
        "Normalized gas tablet",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    _add_curve(
        dataset,
        "NORMALIZED_TOTAL_GAS",
        np.full(depth.shape, 100.0),
        "source:server",
    )
    _add_curve(
        dataset,
        "TG_NORM_CALC",
        np.full(depth.shape, 95.0),
        "calculation:test",
    )
    well = Well("well", "Well", datasets={dataset.dataset_id: dataset})
    layout = TabletLayout(
        [TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120)]
    )
    return ProjectSession(
        project=Project("project", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
        tablet_layouts={dataset.dataset_id: layout},
    )


def test_show_normalized_gas_button_opens_tablet_and_adds_track(qapp) -> None:
    window = MainWindow(language=AppLanguage.RU)
    window.project_controller.session = _session()
    window._bind_project_session()
    window._show_current_dataset()
    workspace = window.interpretation_report_workspace
    index = workspace.normalized_gas_mode.findData(
        NormalizedGasCalculationMode.COMPARE.value
    )
    workspace.normalized_gas_mode.setCurrentIndex(index)
    qapp.processEvents()

    workspace.show_normalized_gas_on_tablet()
    qapp.processEvents()

    assert window.tabs.currentWidget() is window.tablet_view
    layout = window.session.current_tablet_layout
    assert layout is not None
    track = next(item for item in layout.tracks if item.title == "Normalized gas")
    assert track.curve_mnemonics[:2] == [
        "NORMALIZED_TOTAL_GAS",
        "TG_NORM_CALC",
    ]
    assert "NORMALIZED_TOTAL_GAS" in workspace.server_curve_status.text()
    assert "TG_NORM_CALC" in workspace.local_curve_status.text()
    window.close()
