from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest

from geoworkbench.data.las_adapter import LasImportResult
from geoworkbench.data.las_import_report import LasImportReport, LasSourceSnapshot
from geoworkbench.data.lossless_las import parse_lossless_las
from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.project.external_las_insert_controller import ExternalLasInsertController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.depth_axis import analyze_depth_axis
from geoworkbench.services.external_las_insert import ExternalLasCurveSelection


def dataset(dataset_id: str, depth: list[float]) -> Dataset:
    return Dataset(
        dataset_id,
        dataset_id,
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray(depth, dtype=np.float64),
    )


def add_curve(data: Dataset, curve_id: str, mnemonic: str, values: list[float]) -> None:
    data.curves[curve_id] = CurveData(
        CurveMetadata(curve_id, mnemonic, mnemonic, None, None, data.dataset_id),
        np.asarray(values, dtype=np.float64),
    )


def imported(data: Dataset, path: Path) -> LasImportResult:
    raw = b"~V\nVERS.2.0\n~A\n"
    report = LasImportReport(
        LasSourceSnapshot(
            path,
            len(raw),
            sha256(raw).hexdigest(),
            "utf-8",
            "lf",
            ("v", "a"),
            "2.0",
            "NO",
            -999.25,
        ),
        analyze_depth_axis(data.depth),
        (),
    )
    return LasImportResult(data, report, parse_lossless_las(raw))


def test_apply_undo_redo_inserts_curves_and_manifest(monkeypatch, tmp_path: Path) -> None:
    target = dataset("target", [100.0, 101.0])
    source = dataset("source", [100.0, 101.0])
    add_curve(source, "inc", "INCL", [1.0, 2.0])
    session = ProjectSession()
    session.add_dataset(target)
    controller = ExternalLasInsertController(session)
    result = imported(source, tmp_path / "survey.las")
    monkeypatch.setattr(
        "geoworkbench.project.external_las_insert_controller.import_las_with_report",
        lambda _path: result,
    )

    analysis = controller.analyze_file(tmp_path / "survey.las")
    outcome = controller.apply(
        analysis,
        (ExternalLasCurveSelection("inc", "INCL_EXT", "Инклинометрия"),),
    )

    assert outcome.inserted_mnemonics == ("INCL_EXT",)
    assert target.curve_by_mnemonic("INCL_EXT") is not None
    assert any(key.startswith("EXTERNAL_LAS_IMPORT_001_") for key in target.parameters)
    assert controller.can_undo

    controller.undo()
    assert target.curve_by_mnemonic("INCL_EXT") is None
    assert not any(key.startswith("EXTERNAL_LAS_IMPORT_") for key in target.parameters)
    assert controller.can_redo

    controller.redo()
    assert target.curve_by_mnemonic("INCL_EXT") is not None
    assert controller.can_undo


def test_undo_is_blocked_after_inserted_curve_was_edited(monkeypatch, tmp_path: Path) -> None:
    target = dataset("target", [100.0, 101.0])
    source = dataset("source", [100.0, 101.0])
    add_curve(source, "inc", "INCL", [1.0, 2.0])
    session = ProjectSession()
    session.add_dataset(target)
    controller = ExternalLasInsertController(session)
    result = imported(source, tmp_path / "survey.las")
    monkeypatch.setattr(
        "geoworkbench.project.external_las_insert_controller.import_las_with_report",
        lambda _path: result,
    )

    analysis = controller.analyze_file(tmp_path / "survey.las")
    controller.apply(analysis, (ExternalLasCurveSelection("inc", "INCL_EXT"),))
    curve = target.curve_by_mnemonic("INCL_EXT")
    assert curve is not None
    curve.values[0] = 99.0
    curve.version += 1

    with pytest.raises(RuntimeError, match="последующие правки"):
        controller.undo()


def test_manifest_sequence_increments_for_multiple_imports(monkeypatch, tmp_path: Path) -> None:
    target = dataset("target", [100.0, 101.0])
    session = ProjectSession()
    session.add_dataset(target)
    controller = ExternalLasInsertController(session)

    for number in (1, 2):
        source = dataset(f"source-{number}", [100.0, 101.0])
        add_curve(source, f"curve-{number}", f"EXT{number}", [number, number + 1])
        result = imported(source, tmp_path / f"survey-{number}.las")
        monkeypatch.setattr(
            "geoworkbench.project.external_las_insert_controller.import_las_with_report",
            lambda _path, result=result: result,
        )
        analysis = controller.analyze_file(tmp_path / f"survey-{number}.las")
        controller.apply(
            analysis,
            (ExternalLasCurveSelection(f"curve-{number}", f"EXT{number}"),),
        )
        controller.clear_history()

    keys = sorted(key for key in target.parameters if key.startswith("EXTERNAL_LAS_IMPORT_"))
    assert keys[0].startswith("EXTERNAL_LAS_IMPORT_001_")
    assert keys[1].startswith("EXTERNAL_LAS_IMPORT_002_")
