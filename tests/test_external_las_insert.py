from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest

from geoworkbench.data.las_adapter import LasImportResult
from geoworkbench.data.las_import_report import LasImportReport, LasSourceSnapshot
from geoworkbench.data.lossless_las import parse_lossless_las
from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.services.depth_axis import analyze_depth_axis
from geoworkbench.services.external_las_insert import (
    ExternalLasCurveSelection,
    ExternalLasMapping,
    analyze_external_las_insert,
    build_external_las_curves,
)


def make_dataset(dataset_id: str, depth: list[float], *, unit: str = "m") -> Dataset:
    dataset = Dataset(
        dataset_id,
        dataset_id,
        DatasetKind.GTI,
        DepthDomain.MD,
        np.asarray(depth, dtype=np.float64),
    )
    dataset.active_index.unit = unit
    return dataset


def add_curve(
    dataset: Dataset,
    curve_id: str,
    mnemonic: str,
    values: list[float],
    *,
    unit: str = "API",
    description: str | None = None,
) -> CurveData:
    curve = CurveData(
        CurveMetadata(
            curve_id,
            mnemonic,
            mnemonic,
            unit,
            description,
            dataset.dataset_id,
        ),
        np.asarray(values, dtype=np.float64),
    )
    dataset.curves[curve_id] = curve
    return curve


def imported_result(dataset: Dataset, path: Path) -> LasImportResult:
    raw = b"~V\nVERS. 2.0\n~A\n"
    snapshot = LasSourceSnapshot(
        path=path,
        size_bytes=len(raw),
        sha256=sha256(raw).hexdigest(),
        encoding="utf-8",
        newline_style="lf",
        section_names=("v", "a"),
        las_version="2.0",
        wrap="NO",
        null_value=-999.25,
    )
    return LasImportResult(
        dataset,
        LasImportReport(snapshot, analyze_depth_axis(dataset.depth), ()),
        parse_lossless_las(raw),
    )


def test_exact_insert_preserves_both_datasets_and_metadata(tmp_path: Path) -> None:
    source = make_dataset("external", [100.0, 101.0, 102.0])
    add_curve(source, "inc", "INCL", [1.0, 2.0, 3.0], unit="deg", description="Inclination")
    target = make_dataset("target", [100.0, 101.0, 102.0])
    add_curve(target, "rop", "ROP", [10.0, 11.0, 12.0], unit="m/h")
    source_before = source.curve_by_mnemonic("INCL").values.copy()
    target_before = target.curve_by_mnemonic("ROP").values.copy()

    analysis, normalized_source = analyze_external_las_insert(
        imported_result(source, tmp_path / "directional.las"), target
    )
    build = build_external_las_curves(
        normalized_source,
        target,
        analysis,
        (ExternalLasCurveSelection("inc", "DEV_INCL", "Инклинометрия"),),
    )

    assert analysis.mapping is ExternalLasMapping.EXACT
    assert len(build.curves) == 1
    inserted = build.curves[0]
    assert inserted.metadata.original_mnemonic == "DEV_INCL"
    assert inserted.metadata.description == "Инклинометрия"
    assert inserted.metadata.unit == "deg"
    np.testing.assert_allclose(inserted.values, [1.0, 2.0, 3.0])
    np.testing.assert_allclose(source.curve_by_mnemonic("INCL").values, source_before)
    np.testing.assert_allclose(target.curve_by_mnemonic("ROP").values, target_before)
    assert "directional.las" in build.manifest_json


def test_partial_overlap_is_interpolated_only_inside_overlap(tmp_path: Path) -> None:
    source = make_dataset("external", [101.0, 102.0, 103.0])
    add_curve(source, "az", "AZIM", [10.0, 20.0, 30.0], unit="deg")
    target = make_dataset("target", [100.0, 101.0, 101.5, 102.0, 103.0, 104.0])

    analysis, normalized_source = analyze_external_las_insert(
        imported_result(source, tmp_path / "survey.las"), target
    )
    build = build_external_las_curves(
        normalized_source,
        target,
        analysis,
        (ExternalLasCurveSelection("az", "AZIM_EXT"),),
    )

    assert analysis.mapping is ExternalLasMapping.LINEAR_OVERLAP
    np.testing.assert_allclose(
        build.curves[0].values,
        [np.nan, 10.0, 15.0, 20.0, 30.0, np.nan],
        equal_nan=True,
    )


def test_descending_source_is_reversed_in_memory_without_touching_original(tmp_path: Path) -> None:
    source = make_dataset("external", [103.0, 102.0, 101.0])
    add_curve(source, "tvd", "TVD", [30.0, 20.0, 10.0], unit="m")
    target = make_dataset("target", [101.0, 102.0, 103.0])

    analysis, normalized_source = analyze_external_las_insert(
        imported_result(source, tmp_path / "descending.las"), target
    )
    build = build_external_las_curves(
        normalized_source,
        target,
        analysis,
        (ExternalLasCurveSelection(next(iter(normalized_source.curves)), "TVD_EXT"),),
    )

    assert analysis.source_reversed_in_memory is True
    np.testing.assert_allclose(normalized_source.depth, [101.0, 102.0, 103.0])
    np.testing.assert_allclose(build.curves[0].values, [10.0, 20.0, 30.0])
    np.testing.assert_allclose(source.depth, [103.0, 102.0, 101.0])
    np.testing.assert_allclose(source.curve_by_mnemonic("TVD").values, [30.0, 20.0, 10.0])


def test_depth_units_are_converted_before_mapping(tmp_path: Path) -> None:
    source = make_dataset("external", [100.0 / 0.3048, 101.0 / 0.3048], unit="ft")
    add_curve(source, "gr", "GR", [50.0, 60.0])
    target = make_dataset("target", [100.0, 101.0], unit="m")

    analysis, normalized_source = analyze_external_las_insert(
        imported_result(source, tmp_path / "feet.las"), target
    )
    build = build_external_las_curves(
        normalized_source,
        target,
        analysis,
        (ExternalLasCurveSelection("gr", "GR_EXT"),),
    )

    assert analysis.depth_conversion_factor == pytest.approx(0.3048)
    assert analysis.mapping is ExternalLasMapping.EXACT
    np.testing.assert_allclose(build.curves[0].values, [50.0, 60.0])


def test_interpolation_does_not_bridge_null_samples_or_large_depth_gaps(tmp_path: Path) -> None:
    source = make_dataset("external", [100.0, 101.0, 102.0, 110.0])
    add_curve(source, "gr", "GR", [1.0, np.nan, 3.0, 9.0])
    target = make_dataset("target", [100.0, 100.5, 101.0, 101.5, 102.0, 106.0, 110.0])

    analysis, normalized_source = analyze_external_las_insert(
        imported_result(source, tmp_path / "gaps.las"), target
    )
    build = build_external_las_curves(
        normalized_source,
        target,
        analysis,
        (ExternalLasCurveSelection("gr", "GR_EXT"),),
    )

    np.testing.assert_allclose(
        build.curves[0].values,
        [1.0, np.nan, np.nan, np.nan, 3.0, np.nan, 9.0],
        equal_nan=True,
    )


def test_conflicting_mnemonic_gets_safe_suggestion_and_duplicate_output_is_rejected(
    tmp_path: Path,
) -> None:
    source = make_dataset("Directional Survey", [100.0, 101.0])
    add_curve(source, "gr", "GR", [1.0, 2.0])
    target = make_dataset("target", [100.0, 101.0])
    add_curve(target, "old-gr", "GR", [10.0, 20.0])

    analysis, normalized_source = analyze_external_las_insert(
        imported_result(source, tmp_path / "duplicate.las"), target
    )

    assert analysis.candidates[0].suggested_mnemonic.startswith("GR_DIRECTIONAL")
    with pytest.raises(ValueError, match="уже занята"):
        build_external_las_curves(
            normalized_source,
            target,
            analysis,
            (ExternalLasCurveSelection("gr", "GR"),),
        )


def test_vendor_duplicate_and_cyrillic_mnemonics_get_safe_suggestions(tmp_path: Path) -> None:
    from geoworkbench.services.external_las_insert import sanitize_las_mnemonic

    assert sanitize_las_mnemonic("GK:1") == "GK_1"
    assert sanitize_las_mnemonic("GK:2") == "GK_2"
    assert sanitize_las_mnemonic("КС, ННК/ДСР") == "KS_NNK_DSR"

    source = make_dataset("GIS source", [103.0, 102.0, 101.0])
    add_curve(source, "gk1", "GK:1", [30.0, 20.0, 10.0])
    add_curve(source, "gk2", "GK:2", [300.0, 200.0, 100.0])
    target = make_dataset("target", [101.0, 102.0, 103.0])

    analysis, _normalized = analyze_external_las_insert(
        imported_result(source, tmp_path / "vendor.las"), target
    )

    assert analysis.source_reversed_in_memory is True
    assert [item.suggested_mnemonic for item in analysis.candidates] == ["GK_1", "GK_2"]
