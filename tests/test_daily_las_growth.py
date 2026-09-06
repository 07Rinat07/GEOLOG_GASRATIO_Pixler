from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
from hashlib import sha256

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CalculationState,
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    IndexRole,
)
from geoworkbench.services.daily_las_growth import (
    DailyLasGrowthError,
    analyze_daily_las_growth,
    apply_daily_las_growth,
    dataset_append_state_sha256,
    _update_array_digest,
)


def _dataset(
    dataset_id: str,
    index: list[float],
    values: list[float],
    *,
    domain: DepthDomain = DepthDomain.MD,
    well: str = "SG-8",
) -> Dataset:
    dataset = Dataset(
        dataset_id=dataset_id,
        name=dataset_id,
        kind=DatasetKind.GTI,
        depth_domain=domain,
        depth=np.asarray(index, dtype=float),
        headers={"WELL": well},
    )
    curve_id = f"{dataset_id}:rop"
    dataset.curves[curve_id] = CurveData(
        CurveMetadata(
            curve_id=curve_id,
            original_mnemonic="ROP",
            canonical_mnemonic="ROP",
            unit="m/h",
            description="Rate of penetration",
            source_dataset_id=dataset_id,
        ),
        np.asarray(values, dtype=float),
    )
    return dataset


def _add_curve(
    dataset: Dataset,
    mnemonic: str,
    values: list[float],
    *,
    unit: str = "",
    provenance: str = "source",
) -> CurveData:
    curve_id = f"{dataset.dataset_id}:{mnemonic.casefold()}"
    curve = CurveData(
        CurveMetadata(
            curve_id=curve_id,
            original_mnemonic=mnemonic,
            canonical_mnemonic=mnemonic,
            unit=unit,
            description=None,
            source_dataset_id=dataset.dataset_id,
            provenance=provenance,
        ),
        np.asarray(values, dtype=float),
    )
    dataset.curves[curve_id] = curve
    return curve


def test_daily_las_growth_appends_only_new_suffix_and_records_audit() -> None:
    target = _dataset("depth-main", [1000.0, 1000.2, 1000.4], [1.0, 2.0, 3.0])
    source = _dataset("incoming", [1000.4, 1000.6, 1000.8], [3.0, 4.0, 5.0])

    plan = analyze_daily_las_growth(
        target,
        source,
        source_name="SG8_2026-07-24.las",
        source_sha256="a" * 64,
    )
    outcome = apply_daily_las_growth(
        target,
        source,
        plan,
        imported_at=datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc),
    )

    assert plan.rows_added == 2
    assert plan.rows_skipped == 1
    assert np.array_equal(target.active_index.values, [1000.0, 1000.2, 1000.4, 1000.6, 1000.8])
    assert np.array_equal(target.curve_by_mnemonic("ROP").values, [1, 2, 3, 4, 5])
    assert outcome.record is target.append_history[-1]
    assert outcome.record.source_sha256 == "a" * 64
    assert outcome.record.rows_added == 2
    assert target.headers["STRT"] == "1000"
    assert target.headers["STOP"] == "1000.8"
    assert target.headers["STEP"] == "0.2"


def test_reimporting_same_source_hash_is_safe_noop() -> None:
    target = _dataset("depth-main", [1.0, 1.2], [10.0, 20.0])
    source = _dataset("incoming", [1.2, 1.4], [20.0, 30.0])
    first = analyze_daily_las_growth(
        target, source, source_name="daily.las", source_sha256="b" * 64
    )
    apply_daily_las_growth(target, source, first)
    before = target.depth.copy()

    second = analyze_daily_las_growth(
        target, source, source_name="daily.las", source_sha256="b" * 64
    )
    outcome = apply_daily_las_growth(target, source, second)

    assert second.duplicate_source is True
    assert outcome.record is None
    assert np.array_equal(target.depth, before)
    assert len(target.append_history) == 1


def test_time_las_can_never_overwrite_depth_dataset() -> None:
    target = _dataset("depth", [1000.0, 1000.2], [1.0, 2.0])
    source = _dataset(
        "time",
        [0.0, 1.0],
        [1.0, 2.0],
        domain=DepthDomain.TIME,
    )
    assert target.active_index.role is IndexRole.DEPTH
    assert source.active_index.role is IndexRole.TIME

    with pytest.raises(DailyLasGrowthError, match="Импорт запрещён"):
        analyze_daily_las_growth(
            target, source, source_name="time.las", source_sha256="c" * 64
        )


def test_conflicting_overlap_is_rejected_without_partial_mutation() -> None:
    target = _dataset("depth", [10.0, 10.2], [1.0, 2.0])
    source = _dataset("incoming", [10.2, 10.4], [999.0, 3.0])
    depth_before = target.depth.copy()
    curve_before = target.curve_by_mnemonic("ROP").values.copy()

    with pytest.raises(DailyLasGrowthError, match="Конфликт"):
        analyze_daily_las_growth(
            target, source, source_name="bad.las", source_sha256="d" * 64
        )

    assert np.array_equal(target.depth, depth_before)
    assert np.array_equal(target.curve_by_mnemonic("ROP").values, curve_before)
    assert target.append_history == []


@pytest.mark.parametrize("header", ["WELL", "UWI", "API"])
def test_daily_las_growth_rejects_mismatched_stable_well_identifier(header: str) -> None:
    target = _dataset("depth", [10.0, 10.2], [1.0, 2.0])
    source = _dataset("incoming", [10.2, 10.4], [2.0, 3.0])
    target.headers[header] = "stable-id-1"
    source.headers[header] = "stable-id-2"

    with pytest.raises(DailyLasGrowthError, match=header):
        analyze_daily_las_growth(
            target,
            source,
            source_name="wrong-well.las",
            source_sha256="1" * 64,
        )


@pytest.mark.parametrize("header", ["well", "Uwi", "api"])
def test_stable_well_identifier_header_name_is_case_insensitive(header: str) -> None:
    target = _dataset("depth", [10.0, 10.2], [1.0, 2.0])
    source = _dataset("incoming", [10.2, 10.4], [2.0, 3.0])
    target.headers[header] = "stable-id-1"
    source.headers[header.swapcase()] = "stable-id-2"

    with pytest.raises(DailyLasGrowthError, match=header.upper()):
        analyze_daily_las_growth(
            target,
            source,
            source_name="wrong-well.las",
            source_sha256="9" * 64,
        )


@pytest.mark.parametrize("header", ["WELL", "UWI", "API"])
def test_stable_well_identifier_ignores_only_outer_whitespace_and_case(header: str) -> None:
    target = _dataset("depth", [10.0, 10.2], [1.0, 2.0])
    source = _dataset("incoming", [10.2, 10.4], [2.0, 3.0])
    target.headers[header] = "  Stable Id-1  "
    source.headers[header] = "stable id-1"

    plan = analyze_daily_las_growth(
        target,
        source,
        source_name="same-well.las",
        source_sha256="2" * 64,
    )

    assert plan.rows_added == 1


def test_missing_stable_well_identifier_does_not_block_growth() -> None:
    target = _dataset("depth", [10.0, 10.2], [1.0, 2.0])
    source = _dataset("incoming", [10.2, 10.4], [2.0, 3.0])
    target.headers["UWI"] = "stable-id-1"
    source.headers["UWI"] = "  "

    plan = analyze_daily_las_growth(
        target,
        source,
        source_name="missing-uwi.las",
        source_sha256="3" * 64,
    )

    assert plan.rows_added == 1


def test_stable_well_identifier_matching_is_not_fuzzy() -> None:
    target = _dataset("depth", [10.0, 10.2], [1.0, 2.0])
    source = _dataset("incoming", [10.2, 10.4], [2.0, 3.0])
    target.headers["API"] = "12 345"
    source.headers["API"] = "12345"

    with pytest.raises(DailyLasGrowthError, match="API"):
        analyze_daily_las_growth(
            target,
            source,
            source_name="fuzzy-id.las",
            source_sha256="6" * 64,
        )


def test_local_derived_curves_are_not_required_and_are_extended_with_nan() -> None:
    target = _dataset("depth", [10.0, 10.2], [1.0, 2.0])
    calculated = _add_curve(
        target,
        "DEXP",
        [1.1, 1.2],
        provenance="calculation:dexp:1.0",
    )
    custom = _add_curve(
        target,
        "USER_RATIO",
        [2.1, 2.2],
        provenance="custom-formula:user-ratio:1.0",
    )
    source = _dataset("incoming", [10.2, 10.4, 10.6], [2.0, 3.0, 4.0])

    plan = analyze_daily_las_growth(
        target,
        source,
        source_name="daily.las",
        source_sha256="4" * 64,
    )
    apply_daily_las_growth(target, source, plan)

    assert plan.curve_mnemonics == ("ROP",)
    assert np.array_equal(target.curve_by_mnemonic("ROP").values, [1.0, 2.0, 3.0, 4.0])
    assert np.array_equal(calculated.values[:2], [1.1, 1.2])
    assert np.array_equal(custom.values[:2], [2.1, 2.2])
    assert np.isnan(calculated.values[2:]).all()
    assert np.isnan(custom.values[2:]).all()
    assert calculated.state is CalculationState.STALE
    assert custom.state is CalculationState.STALE
    assert all(curve.values.shape == target.depth.shape for curve in target.curves.values())


@pytest.mark.parametrize("provenance", ["user", "transfer:other:gr", "external-las:abc:GR"])
def test_local_project_curve_does_not_block_daily_source_schema(
    provenance: str,
) -> None:
    target = _dataset("depth", [10.0, 10.2], [1.0, 2.0])
    local = _add_curve(
        target,
        "LOCAL_NOTE_CURVE",
        [8.0, 9.0],
        provenance=provenance,
    )
    source = _dataset("incoming", [10.2, 10.4], [2.0, 3.0])

    plan = analyze_daily_las_growth(
        target,
        source,
        source_name="daily.las",
        source_sha256="8" * 64,
    )
    apply_daily_las_growth(target, source, plan)

    assert plan.curve_mnemonics == ("ROP",)
    assert np.array_equal(local.values[:2], [8.0, 9.0])
    assert np.isnan(local.values[2])


def test_local_derived_exemption_does_not_relax_native_curve_units() -> None:
    target = _dataset("depth", [10.0, 10.2], [1.0, 2.0])
    _add_curve(target, "DEXP", [1.1, 1.2], provenance="calculation:dexp:1.0")
    source = _dataset("incoming", [10.2, 10.4], [2.0, 3.0])
    source_rop = source.curve_by_mnemonic("ROP")
    assert source_rop is not None
    source_rop.metadata = CurveMetadata(
        curve_id="incoming:rop",
        original_mnemonic="ROP",
        canonical_mnemonic="ROP",
        unit="ft/h",
        description="Rate of penetration",
        source_dataset_id="incoming",
    )

    with pytest.raises(DailyLasGrowthError, match="Единица кривой ROP"):
        analyze_daily_las_growth(
            target,
            source,
            source_name="wrong-unit.las",
            source_sha256="5" * 64,
        )


@pytest.mark.parametrize(
    ("schema_change", "message"),
    [("missing", "нет обязательных кривых"), ("extra", "лишние кривые")],
)
def test_local_derived_exemption_preserves_exact_native_schema(
    schema_change: str,
    message: str,
) -> None:
    target = _dataset("depth", [10.0, 10.2], [1.0, 2.0])
    _add_curve(target, "DEXP", [1.1, 1.2], provenance="calculation:dexp:1.0")
    source = _dataset("incoming", [10.2, 10.4], [2.0, 3.0])
    if schema_change == "missing":
        source.curves.clear()
    else:
        _add_curve(source, "GR", [80.0, 81.0], unit="API")

    with pytest.raises(DailyLasGrowthError, match=message):
        analyze_daily_las_growth(
            target,
            source,
            source_name="wrong-schema.las",
            source_sha256="7" * 64,
        )


def test_growth_of_one_dataset_does_not_touch_other_depth_or_time_datasets() -> None:
    first_depth = _dataset("depth-a", [0.0, 0.2], [1.0, 2.0])
    second_depth = _dataset("depth-b", [50.0, 50.5], [5.0, 6.0])
    time_data = _dataset("time-a", [0.0, 1.0], [7.0, 8.0], domain=DepthDomain.TIME)
    source = _dataset("incoming", [0.2, 0.4], [2.0, 3.0])
    second_before = second_depth.depth.copy()
    time_before = time_data.depth.copy()

    plan = analyze_daily_las_growth(
        first_depth, source, source_name="daily.las", source_sha256="e" * 64
    )
    apply_daily_las_growth(first_depth, source, plan)

    assert np.array_equal(second_depth.depth, second_before)
    assert np.array_equal(time_data.depth, time_before)


def test_append_history_survives_project_round_trip(tmp_path) -> None:
    from geoworkbench.domain.models import Project, Well
    from geoworkbench.storage.atomic_json import save_project
    from geoworkbench.storage.project_codec import load_project

    target = _dataset("depth-main", [1000.0, 1000.2], [1.0, 2.0])
    source = _dataset("incoming", [1000.2, 1000.4], [2.0, 3.0])
    plan = analyze_daily_las_growth(
        target,
        source,
        source_name="SG8_2026-07-24.las",
        source_sha256="f" * 64,
    )
    apply_daily_las_growth(
        target,
        source,
        plan,
        imported_at=datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc),
    )
    project = Project(
        "project-1",
        "Daily LAS growth",
        wells={"well-1": Well("well-1", "SG-8", datasets={target.dataset_id: target})},
    )
    project_path = tmp_path / "daily-growth.geolog.json"

    save_project(project, project_path)
    restored = load_project(project_path)

    restored_target = restored.wells["well-1"].datasets["depth-main"]
    assert len(restored_target.append_history) == 1
    assert restored_target.append_history[0] == target.append_history[0]
    assert np.array_equal(restored_target.depth, target.depth)
    assert np.array_equal(
        restored_target.curve_by_mnemonic("ROP").values,
        target.curve_by_mnemonic("ROP").values,
    )


@pytest.mark.parametrize("changed_input", [
    "old_target_value", "new_source_value", "local_value", "local_provenance",
    "curve_version", "curve_state", "both_curve_units", "both_axis_units",
    "target_header", "source_header", "source_identity", "depth_projection",
])
def test_preview_rejects_changed_inputs_even_when_row_summary_is_unchanged(
    changed_input: str,
) -> None:
    target = _dataset("target", [10.0, 11.0], [1.0, 2.0])
    source = _dataset("source", [11.0, 12.0], [2.0, 3.0])
    local = _add_curve(target, "LOCAL", [8.0, 9.0], provenance="user")
    plan = analyze_daily_las_growth(
        target, source, source_name="daily.las", source_sha256="a" * 64,
    )
    target_curve = target.curve_by_mnemonic("ROP")
    source_curve = source.curve_by_mnemonic("ROP")
    assert target_curve is not None and source_curve is not None
    if changed_input == "old_target_value":
        target_curve.values[0] = 99
    elif changed_input == "new_source_value":
        source_curve.values[-1] = 99
    elif changed_input == "local_value":
        local.values[0] = 99
    elif changed_input == "local_provenance":
        local.metadata = replace(local.metadata, provenance="calculation:test:1")
    elif changed_input == "curve_version":
        target_curve.version += 1
    elif changed_input == "curve_state":
        local.state = CalculationState.STALE
    elif changed_input == "both_curve_units":
        for curve in (target_curve, source_curve):
            curve.metadata = replace(curve.metadata, unit="ft/h")
    elif changed_input == "both_axis_units":
        target.active_index.unit = source.active_index.unit = "ft"
    elif changed_input == "target_header":
        target.headers["UWI"] = "new-well-identity"
    elif changed_input == "source_header":
        source.headers["UWI"] = "new-well-identity"
    elif changed_input == "source_identity":
        source.dataset_id = "replacement"
    elif changed_input == "depth_projection":
        target.depth = target.depth.copy() + 1

    refreshed = analyze_daily_las_growth(
        target, source, source_name="daily.las", source_sha256="a" * 64,
    )
    assert (refreshed.rows_added, refreshed.rows_skipped, refreshed.new_row_indices) == (
        plan.rows_added, plan.rows_skipped, plan.new_row_indices,
    )
    before_target = dataset_append_state_sha256(target)
    before_source = dataset_append_state_sha256(source)
    with pytest.raises(DailyLasGrowthError, match="после предварительного анализа"):
        apply_daily_las_growth(target, source, plan)
    assert dataset_append_state_sha256(target) == before_target
    assert dataset_append_state_sha256(source) == before_source
    assert not target.append_history


@pytest.mark.parametrize("descending", [False, True])
def test_unchanged_preview_accepts_nan_and_reordered_containers(descending: bool) -> None:
    sign = -1 if descending else 1
    target = _dataset("target", [sign * 10., sign * 11.], [float("nan"), 2.])
    source = _dataset("source", [sign * 11., sign * 12.], [2., float("nan")])
    _add_curve(target, "LOCAL", [8., float("nan")], provenance="user")
    plan = analyze_daily_las_growth(
        target, source, source_name="daily.las", source_sha256="a" * 64,
    )
    target.curves = dict(reversed(list(target.curves.items())))
    target.name = "Presentation name changed"
    outcome = apply_daily_las_growth(target, source, plan)
    assert outcome.record is not None
    assert outcome.record.rows_added == 1


@pytest.mark.parametrize("layout", ["contiguous", "strided", "reverse", "empty", "datetime"])
def test_bounded_array_hash_preserves_historical_audit_digest(layout: str) -> None:
    values = np.arange(300_001, dtype=np.float64)
    if layout == "strided":
        values = values[::2]
    elif layout == "reverse":
        values = values[::-1]
    elif layout == "empty":
        values = values[:0]
    elif layout == "datetime":
        values = values.astype("datetime64[ns]")
    expected = sha256()
    expected.update(values.dtype.str.encode("ascii"))
    expected.update(str(values.shape).encode("ascii"))
    expected.update(np.ascontiguousarray(values).tobytes())
    actual = sha256()
    _update_array_digest(actual, values)
    assert actual.hexdigest() == expected.hexdigest()
