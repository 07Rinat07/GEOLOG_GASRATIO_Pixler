from __future__ import annotations

from hashlib import sha256
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import get_ident

import numpy as np
import pytest

from geoworkbench.data.las_adapter import LasImportResult, export_las, import_las_with_report
from geoworkbench.calculations.custom_formula import CustomFormulaDefinition
from geoworkbench.data.las_import_report import LasImportReport, LasSourceSnapshot
from geoworkbench.data.lossless_las import parse_lossless_las
from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.project.external_las_insert_controller import ExternalLasInsertController
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.services.depth_axis import analyze_depth_axis
from geoworkbench.services.edit_history import CommandHistory, CurveEditCommand
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


def test_create_copy_keeps_target_unchanged_and_selects_new_dataset(
    monkeypatch, tmp_path: Path
) -> None:
    target = dataset("target", [100.0, 101.0])
    add_curve(target, "rop", "ROP", [10.0, 11.0])
    source = dataset("source", [101.0, 100.0])
    add_curve(source, "gk", "GK:1", [2.0, 1.0])
    session = ProjectSession()
    session.add_dataset(target)
    original_layout = TabletLayout(
        [
            TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
            TrackDefinition(
                "gti", "GTI", TrackKind.CURVE, width=220,
                curve_mnemonics=["ROP"],
            ),
        ],
        visible_depth_top=100.0,
        visible_depth_bottom=101.0,
    )
    session.tablet_layouts[target.dataset_id] = original_layout
    controller = ExternalLasInsertController(session)
    result = imported(source, tmp_path / "gis.las")
    monkeypatch.setattr(
        "geoworkbench.project.external_las_insert_controller.import_las_with_report",
        lambda _path: result,
    )

    analysis = controller.analyze_file(tmp_path / "gis.las")
    candidate = analysis.candidates[0]
    outcome = controller.create_copy(
        analysis,
        (ExternalLasCurveSelection(candidate.source_curve_id, candidate.suggested_mnemonic),),
        name="combined",
    )

    assert target.curve_by_mnemonic("GK_1") is None
    assert target.curve_by_mnemonic("ROP") is not None
    assert outcome.dataset is session.current_dataset
    assert outcome.dataset.dataset_id != target.dataset_id
    copied_layout = session.current_tablet_layout
    assert copied_layout is not None
    assert copied_layout is not original_layout
    assert session.tablet_layouts[target.dataset_id] is original_layout
    assert copied_layout.tracks[1].curve_mnemonics == ["ROP"]
    copied_layout.tracks[1].curve_mnemonics.append("GK_1")
    assert original_layout.tracks[1].curve_mnemonics == ["ROP"]
    assert (copied_layout.visible_depth_top, copied_layout.visible_depth_bottom) == (
        100.0, 101.0,
    )
    assert outcome.dataset.source_path is None
    assert outcome.dataset.curve_by_mnemonic("ROP") is not None
    inserted = outcome.dataset.curve_by_mnemonic("GK_1")
    assert inserted is not None
    np.testing.assert_allclose(inserted.values, [1.0, 2.0])
    assert any(
        key.startswith("EXTERNAL_LAS_IMPORT_") for key in outcome.dataset.parameters
    )


def test_copy_preparation_runs_in_worker_before_project_commit(monkeypatch, tmp_path):
    target = dataset("target", [100.0, 101.0])
    source = dataset("source", [100.0, 101.0])
    add_curve(source, "inc", "INCL", [1.0, 2.0])
    session = ProjectSession()
    session.add_dataset(target)
    controller = ExternalLasInsertController(session)
    monkeypatch.setattr(
        "geoworkbench.project.external_las_insert_controller.import_las_with_report",
        lambda _path: imported(source, tmp_path / "gis.las"),
    )
    analysis = controller.analyze_file(tmp_path / "gis.las")
    main_thread = get_ident()
    workers = []

    def prepare(operation):
        def run():
            workers.append(get_ident())
            prepared = operation()
            assert session.current_dataset is target
            assert len(session.current_well.datasets) == 1
            return prepared
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(run).result()

    selection = ExternalLasCurveSelection("inc", "INCL")
    outcome = controller.create_copy(analysis, (selection,), prepare=prepare)
    assert workers and workers[0] != main_thread
    assert session.current_dataset is outcome.dataset
    np.testing.assert_allclose(outcome.dataset.curve_by_mnemonic("INCL").values, [1.0, 2.0])


def test_copy_aborts_if_target_changes_during_preparation(monkeypatch, tmp_path):
    target = dataset("target", [100.0, 101.0])
    source = dataset("source", [100.0, 101.0])
    add_curve(source, "inc", "INCL", [1.0, 2.0])
    session = ProjectSession()
    session.add_dataset(target)
    controller = ExternalLasInsertController(session)
    monkeypatch.setattr(
        "geoworkbench.project.external_las_insert_controller.import_las_with_report",
        lambda _path: imported(source, tmp_path / "gis.las"),
    )
    analysis = controller.analyze_file(tmp_path / "gis.las")
    other = dataset("other", [100.0, 101.0])

    def prepare(operation):
        prepared = operation()
        session.add_dataset(other)
        return prepared

    with pytest.raises(RuntimeError, match="изменился"):
        controller.create_copy(analysis, (ExternalLasCurveSelection("inc", "INCL"),), prepare=prepare)
    assert session.current_dataset is other
    assert set(session.current_well.datasets) == {target.dataset_id, other.dataset_id}


def test_worker_recalculation_matches_existing_gas_calculation(monkeypatch, tmp_path):
    target = dataset("target", [100.0, 101.0])
    for mnemonic, values in (("C1", [30.0, 40.0]), ("C2", [5.0, 6.0]), ("C3", [2.0, 3.0])):
        add_curve(target, mnemonic, mnemonic, values)
    source = dataset("source", [100.0, 101.0])
    add_curve(source, "gr", "GR", [10.0, 20.0])
    monkeypatch.setattr(
        "geoworkbench.project.external_las_insert_controller.import_las_with_report",
        lambda _path: imported(deepcopy(source), tmp_path / "gis.las"),
    )
    outputs = []
    for threaded in (False, True):
        session = ProjectSession()
        receiver = deepcopy(target)
        session.add_dataset(receiver)
        controller = ExternalLasInsertController(session)
        analysis = controller.analyze_file(tmp_path / "gis.las")
        selection = ExternalLasCurveSelection("gr", "GR")
        if threaded:
            def prepare(operation):
                with ThreadPoolExecutor(max_workers=1) as executor:
                    return executor.submit(operation).result()
            result = controller.create_copy(analysis, (selection,), prepare=prepare)
        else:
            result = controller.create_copy(analysis, (selection,))
        outputs.append(result)
        assert receiver.curve_by_mnemonic("GR") is None
    baseline, threaded_result = outputs
    assert baseline.recalculation == threaded_result.recalculation
    assert baseline.recalculation.recalculated_mnemonics
    baseline_curves = {c.metadata.original_mnemonic: c for c in baseline.dataset.curves.values()}
    worker_curves = {c.metadata.original_mnemonic: c for c in threaded_result.dataset.curves.values()}
    assert baseline_curves.keys() == worker_curves.keys()
    for mnemonic, curve in baseline_curves.items():
        np.testing.assert_allclose(curve.values, worker_curves[mnemonic].values, equal_nan=True)
    assert baseline.dataset.gas_conditioning_qc == threaded_result.dataset.gas_conditioning_qc


def test_copy_rejects_formula_changes_during_preparation(monkeypatch, tmp_path):
    target = dataset("target", [100.0, 101.0])
    source = dataset("source", [100.0, 101.0])
    add_curve(source, "gr", "GR", [10.0, 20.0])
    session = ProjectSession()
    session.add_dataset(target)
    controller = ExternalLasInsertController(session)
    monkeypatch.setattr(
        "geoworkbench.project.external_las_insert_controller.import_las_with_report",
        lambda _path: imported(source, tmp_path / "gis.las"),
    )
    analysis = controller.analyze_file(tmp_path / "gis.las")

    def prepare(operation):
        prepared = operation()
        session.project.custom_formulas["new"] = CustomFormulaDefinition(
            "new", "New", "GR + 1", "NEW", "%",
        )
        return prepared

    with pytest.raises(RuntimeError, match="Формулы изменились"):
        controller.create_copy(analysis, (ExternalLasCurveSelection("gr", "GR"),), prepare=prepare)
    assert session.current_dataset is target
    assert len(session.current_well.datasets) == 1


@pytest.mark.parametrize("threaded", [False, True])
def test_custom_formula_remains_calculated_after_insert_and_project_reopen(
    monkeypatch, tmp_path, threaded,
):
    target = dataset("target", [100.0, 101.0])
    add_curve(target, "c1", "C1", [10.0, 20.0])
    add_curve(target, "custom", "CUSTOM", [0.0, 0.0])
    target.curves["custom"].metadata = replace(
        target.curves["custom"].metadata, provenance="custom-formula:custom:1",
    )
    source = dataset("source", [100.0, 101.0])
    add_curve(source, "gr", "GR", [10.0, 20.0])
    session = ProjectSession()
    session.project.custom_formulas["custom"] = CustomFormulaDefinition(
        "custom", "Custom", "C1 + 1", "CUSTOM", "%",
    )
    session.add_dataset(target)
    controller = ExternalLasInsertController(session)
    monkeypatch.setattr(
        "geoworkbench.project.external_las_insert_controller.import_las_with_report",
        lambda _path: imported(source, tmp_path / "gis.las"),
    )
    analysis = controller.analyze_file(tmp_path / "gis.las")
    def prepare(operation):
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(operation).result()
    result = controller.create_copy(
        analysis, (ExternalLasCurveSelection("gr", "GR"),),
        prepare=prepare if threaded else None,
    )
    assert "CUSTOM" in result.recalculation.recalculated_mnemonics
    np.testing.assert_allclose(result.dataset.curve_by_mnemonic("CUSTOM").values, [11.0, 21.0])
    np.testing.assert_allclose(target.curve_by_mnemonic("CUSTOM").values, [0.0, 0.0])
    project_path = tmp_path / "combined.geologpkg"
    ProjectController(session=session).save_project(project_path)
    reopened = ProjectController().open_project(project_path)
    reopened.current_dataset_id = result.dataset.dataset_id
    curve = reopened.current_dataset.curve_by_mnemonic("CUSTOM")
    assert curve.metadata.provenance.startswith("custom-formula:custom:1:external-las-copy:target:custom")
    np.testing.assert_allclose(curve.values, [11.0, 21.0])


def test_copy_cleans_only_its_own_partial_commit_on_error(monkeypatch, tmp_path):
    target = dataset("target", [100.0, 101.0])
    source = dataset("source", [100.0, 101.0])
    add_curve(source, "gr", "GR", [10.0, 20.0])
    session = ProjectSession()
    session.add_dataset(target)
    session.dirty = False
    controller = ExternalLasInsertController(session)
    monkeypatch.setattr(
        "geoworkbench.project.external_las_insert_controller.import_las_with_report",
        lambda _path: imported(source, tmp_path / "gis.las"),
    )
    def fail(*args, **kwargs):
        raise RuntimeError("recalculation failed")
    monkeypatch.setattr(
        "geoworkbench.project.external_las_insert_controller.recalculate_existing_dependents", fail,
    )
    analysis = controller.analyze_file(tmp_path / "gis.las")
    with pytest.raises(RuntimeError, match="recalculation failed"):
        controller.create_copy(analysis, (ExternalLasCurveSelection("gr", "GR"),))
    assert session.current_dataset is target
    assert set(session.current_well.datasets) == {target.dataset_id}
    assert session.dirty is False


def test_shared_history_keeps_external_las_undo_domain_safe(
    monkeypatch, tmp_path: Path
) -> None:
    target = dataset("target", [100.0, 101.0])
    source = dataset("source", [100.0, 101.0])
    add_curve(source, "inc", "INCL", [1.0, 2.0])
    history = CommandHistory()
    session = ProjectSession()
    session.add_dataset(target)
    controller = ExternalLasInsertController(session, shared_history=history)
    result = imported(source, tmp_path / "survey.las")
    monkeypatch.setattr(
        "geoworkbench.project.external_las_insert_controller.import_las_with_report",
        lambda _path: result,
    )

    analysis = controller.analyze_file(tmp_path / "survey.las")
    controller.apply(analysis, (ExternalLasCurveSelection("inc", "INCL_EXT"),))
    inserted = target.curve_by_mnemonic("INCL_EXT")
    assert inserted is not None
    assert controller.can_undo is True

    history.execute(
        CurveEditCommand.create(
            inserted,
            np.array([0], dtype=np.int64),
            np.array([9.0], dtype=np.float64),
        )
    )

    assert controller.can_undo is False
    history.undo()
    assert inserted.values[0] == 1.0
    assert controller.can_undo is True

    controller.undo()

    assert target.curve_by_mnemonic("INCL_EXT") is None


def test_shared_history_supports_multiple_external_las_inserts(
    monkeypatch, tmp_path: Path
) -> None:
    target = dataset("target", [100.0, 101.0])
    history = CommandHistory()
    session = ProjectSession()
    session.add_dataset(target)
    controller = ExternalLasInsertController(session, shared_history=history)

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

    assert target.curve_by_mnemonic("EXT1") is not None
    assert target.curve_by_mnemonic("EXT2") is not None

    controller.undo()
    assert target.curve_by_mnemonic("EXT2") is None
    assert target.curve_by_mnemonic("EXT1") is not None

    controller.undo()
    assert target.curve_by_mnemonic("EXT1") is None

    controller.redo()
    controller.redo()
    assert target.curve_by_mnemonic("EXT1") is not None
    assert target.curve_by_mnemonic("EXT2") is not None


@pytest.mark.parametrize("gis_source_descending", (False, True))
def test_bottom_up_receiver_combined_las_export_roundtrip_preserves_depth_values(
    monkeypatch, tmp_path: Path, gis_source_descending: bool,
) -> None:
    # A typical GIS log can run bottom-up; the receiver may also be a
    # bottom-up LAS. Both output channels must retain their depth pairing.
    target = dataset("target", [103.0, 102.0, 101.0])
    add_curve(target, "rop", "ROP", [7.0, 8.0, 9.0])
    source_depth = [103.0, 102.0, 101.0] if gis_source_descending else [
        101.0, 102.0, 103.0,
    ]
    source_values = [30.0, 20.0, 10.0] if gis_source_descending else [10.0, 20.0, 30.0]
    source = dataset("gis", source_depth)
    add_curve(source, "gr", "GK", source_values)

    session = ProjectSession()
    session.add_dataset(target)
    controller = ExternalLasInsertController(session)
    imported_source = imported(source, tmp_path / "survey-gis.las")
    monkeypatch.setattr(
        "geoworkbench.project.external_las_insert_controller.import_las_with_report",
        lambda _path: imported_source,
    )

    analysis = controller.analyze_file(tmp_path / "survey-gis.las")
    assert analysis.target_original_direction.value == "descending"
    assert analysis.source_reversed_in_memory is gis_source_descending

    # The dialog submits candidate IDs from analysis; descending source
    # normalization intentionally assigns new IDs to its in-memory copy.
    selected_curve_id = analysis.candidates[0].source_curve_id
    combined = controller.create_copy(
        analysis, (ExternalLasCurveSelection(selected_curve_id, "GK_GIS"),),
        name="GIS plus ROP",
    ).dataset
    np.testing.assert_allclose(combined.depth, [103.0, 102.0, 101.0])
    np.testing.assert_allclose(combined.curve_by_mnemonic("GK_GIS").values, [30, 20, 10])
    np.testing.assert_allclose(combined.curve_by_mnemonic("ROP").values, [7, 8, 9])
    np.testing.assert_allclose(target.depth, [103.0, 102.0, 101.0])
    assert target.curve_by_mnemonic("GK_GIS") is None

    output = tmp_path / "gis_plus_gti.las"
    export_las(combined, output)
    reimported = import_las_with_report(output).dataset
    assert reimported.curve_by_mnemonic("GK_GIS") is not None
    assert reimported.curve_by_mnemonic("ROP") is not None
    np.testing.assert_allclose(reimported.depth, [103.0, 102.0, 101.0])
    np.testing.assert_allclose(
        reimported.curve_by_mnemonic("GK_GIS").values, [30.0, 20.0, 10.0],
    )
    np.testing.assert_allclose(
        reimported.curve_by_mnemonic("ROP").values, [7.0, 8.0, 9.0],
    )
