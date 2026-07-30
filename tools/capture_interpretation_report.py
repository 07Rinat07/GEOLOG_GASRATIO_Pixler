from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    CuttingsSample,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
    NormalizedGasCalculationMode,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture normalized-gas interpretation workspace screenshots"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def _dark_palette() -> QPalette:
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#171a1f",
        QPalette.ColorRole.WindowText: "#f4f7fb",
        QPalette.ColorRole.Base: "#20242b",
        QPalette.ColorRole.AlternateBase: "#262b34",
        QPalette.ColorRole.ToolTipBase: "#20242b",
        QPalette.ColorRole.ToolTipText: "#f4f7fb",
        QPalette.ColorRole.Text: "#f4f7fb",
        QPalette.ColorRole.Button: "#262b34",
        QPalette.ColorRole.ButtonText: "#f4f7fb",
        QPalette.ColorRole.Highlight: "#4c9dff",
        QPalette.ColorRole.HighlightedText: "#07111f",
        QPalette.ColorRole.Mid: "#546070",
    }
    for role, value in colors.items():
        palette.setColor(role, QColor(value))
    return palette


def _add_curve(
    dataset: Dataset,
    mnemonic: str,
    values: np.ndarray,
    unit: str,
    provenance: str,
) -> None:
    dataset.curves[mnemonic] = CurveData(
        CurveMetadata(
            mnemonic,
            mnemonic,
            mnemonic,
            unit,
            mnemonic,
            dataset.dataset_id,
            provenance,
        ),
        np.asarray(values, dtype=np.float64),
    )


def _session() -> ProjectSession:
    depth = np.arange(1_000.0, 1_100.0)
    dataset = Dataset(
        "normalized-gas-acceptance",
        "Normalized gas acceptance",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    constants = {
        "C1": (80.0, "%"),
        "C2": (10.0, "%"),
        "C3": (5.0, "%"),
        "IC4": (1.0, "%"),
        "NC4": (2.0, "%"),
        "IC5": (1.0, "%"),
        "NC5": (1.0, "%"),
        "ROP": (60.0, "ft/h"),
        "BIT": (10.0, "in"),
        "FLOW": (500.0, "gpm"),
    }
    for mnemonic, (value, unit) in constants.items():
        _add_curve(
            dataset,
            mnemonic,
            np.full(depth.shape, value),
            unit,
            "source:acceptance",
        )
    server = np.ones(depth.shape)
    server[42:47] = (40.0, 90.0, 125.0, 85.0, 45.0)
    _add_curve(
        dataset,
        "NORMALIZED_TOTAL_GAS",
        server,
        "normalized gas units",
        "source:server",
    )
    session = ProjectSession()
    well = session.add_dataset(dataset, "Acceptance well")
    well.cuttings.append(
        CuttingsSample(
            "acceptance-lba",
            1_041.5,
            1_047.5,
            lba_group=2,
            lba_type_id="ПБ",
            lba_intensity=3,
            lba_color="ЖК — жёлто-коричневый",
        )
    )
    return session


def _capture(
    language: AppLanguage,
    output: Path,
    application: QApplication,
) -> None:
    controller = InterpretationCalculationController(_session())
    controller.calculate_normalized_gas(
        normalized_gas_mode=NormalizedGasCalculationMode.COMPARE
    )
    widget = InterpretationReportWorkspace(controller, language=language)
    widget.resize(1680, 980)
    widget.show()
    application.processEvents()
    widget.refresh()
    application.processEvents()

    pixmap = widget.grab()
    target = output / f"{language.value}-normalized-gas-interpretation.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    if pixmap.isNull() or not pixmap.save(str(target), "PNG"):
        raise RuntimeError(f"Failed to capture interpretation screenshot: {target}")
    widget.close()
    application.processEvents()


def main() -> int:
    args = _arguments()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    application = QApplication.instance() or QApplication([])
    application.setStyle("Fusion")
    application.setPalette(_dark_palette())
    for language in (AppLanguage.RU, AppLanguage.KK, AppLanguage.EN):
        _capture(language, output, application)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
