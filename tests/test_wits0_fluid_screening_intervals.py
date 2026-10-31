"""WITS-INTERP-01: no invented coverage or mixed-source fluid intervals."""

from dataclasses import FrozenInstanceError, replace

import pytest

from geoworkbench.services.gas_ratio_interpretation import classify_gas_ratio
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.wits0_fluid_screening import project_wits0_fluid_screening
from geoworkbench.domain.acquisition import (
    AcquisitionDataRowPayload,
    AcquisitionDatasetSchema,
    AcquisitionIndexSchema,
    AcquisitionRecord,
    AcquisitionRecordKind,
    AcquisitionSession,
)
from geoworkbench.domain.models import DatasetKind, DepthDomain, IndexRole, IndexType
from geoworkbench.services.wits0_fluid_screening_intervals import (
    Wits0FluidScreeningPoint,
    Wits0FluidScreeningSample,
    bind_wits0_fluid_screening_point,
    verify_wits0_fluid_screening_point,
    snapshot_wits0_fluid_screening_points,
    coalesce_wits0_fluid_screening,
)
from geoworkbench.services.wits0_gas_context import Wits0GasOriginKind
from geoworkbench.services.wits0_manual_gas_context import Wits0GasContextAxis


SOURCE = "dataset-1/session-1/source-01"
AXIS = Wits0GasContextAxis.DEPTH


def _projection(
    origin: Wits0GasOriginKind = Wits0GasOriginKind.BACKGROUND,
    *,
    wetness: float = 1.0,
):
    return project_wits0_fluid_screening(
        classify_gas_ratio(wetness=wetness, balance=3.0, character=0.2),
        pixler=None,
        wetness_robust_z=None,
        origin_kind=origin,
    )


def _sample(
    sequence: int,
    start: float,
    end: float,
    *,
    screening=None,
    source_key: str = SOURCE,
    axis: Wits0GasContextAxis = AXIS,
) -> Wits0FluidScreeningSample:
    return Wits0FluidScreeningSample(
        source_key=source_key,
        axis=axis,
        start=start,
        end=end,
        sequence=sequence,
        screening=_projection() if screening is None else screening,
    )


def _coalesce(*samples: Wits0FluidScreeningSample):
    return coalesce_wits0_fluid_screening(samples, source_key=SOURCE, axis=AXIS)


def test_adjacent_equal_screening_joins_without_reclassification() -> None:
    first = _sample(10, 100.0, 100.5)
    second = _sample(11, 100.5, 101.0)
    third = _sample(12, 101.0, 101.25)
    original = (first, second, third)

    intervals = _coalesce(*original)

    assert len(intervals) == 1
    interval = intervals[0]
    assert (interval.start, interval.end) == (100.0, 101.25)
    assert (interval.first_sequence, interval.last_sequence, interval.sample_count) == (
        10, 12, 3
    )
    assert interval.source_key == SOURCE
    assert interval.axis is AXIS
    assert interval.screening == first.screening
    assert interval.screening.badge_text(AppLanguage.EN).startswith("Preliminary indicator:")
    assert original == (first, second, third)
    assert _coalesce(*original) == intervals


def test_real_gaps_skipped_sequences_and_nonidentical_boundaries_stay_separate() -> None:
    intervals = _coalesce(
        _sample(1, 100.0, 100.5),
        _sample(2, 100.6, 101.0),  # measured gap
        _sample(4, 101.0, 101.5),  # skipped source sequence
        _sample(5, 101.5000000001, 102.0),  # not exactly touching
    )
    assert [(item.start, item.end, item.sample_count) for item in intervals] == [
        (100.0, 100.5, 1),
        (100.6, 101.0, 1),
        (101.0, 101.5, 1),
        (101.5000000001, 102.0, 1),
    ]


def test_fluid_or_operational_origin_change_does_not_hide_provenance() -> None:
    background = _projection()
    connection = _projection(Wits0GasOriginKind.CONNECTION_GAS)
    liquid = _projection(wetness=20.0)
    intervals = _coalesce(
        _sample(1, 100.0, 100.5, screening=background),
        _sample(2, 100.5, 101.0, screening=connection),
        _sample(3, 101.0, 101.5, screening=liquid),
    )

    assert len(intervals) == 3
    assert [item.screening.origin_kind for item in intervals] == [
        Wits0GasOriginKind.BACKGROUND,
        Wits0GasOriginKind.CONNECTION_GAS,
        Wits0GasOriginKind.BACKGROUND,
    ]
    assert intervals[1].screening.formation_show_marker is False
    assert all(item.sample_count == 1 for item in intervals)


def test_source_and_axis_must_match_exactly() -> None:
    with pytest.raises(ValueError, match="source and axis"):
        _coalesce(_sample(1, 0.0, 1.0, source_key="another-session"))
    with pytest.raises(ValueError, match="source and axis"):
        _coalesce(
            _sample(
                1, 0.0, 1.0, axis=Wits0GasContextAxis.ELAPSED_TIME
            )
        )
    with pytest.raises(ValueError, match="source_key"):
        coalesce_wits0_fluid_screening((), source_key="", axis=AXIS)
    with pytest.raises(ValueError, match="axis"):
        coalesce_wits0_fluid_screening((), source_key=SOURCE, axis="depth")


@pytest.mark.parametrize(
    "start,end",
    [
        (0.0, 0.0),
        (2.0, 1.0),
        (-1.0, 0.0),
        (float("nan"), 1.0),
        (0.0, float("inf")),
        (True, 1.0),
        ("0", 1.0),
    ],
)
def test_invalid_coverage_rejected_before_coalescing(start, end) -> None:
    with pytest.raises(ValueError):
        _sample(1, start, end)


@pytest.mark.parametrize("sequence", [0, -1, True, 1.0, "1"])
def test_invalid_source_sequence_rejected(sequence) -> None:
    with pytest.raises(ValueError, match="sequence"):
        _sample(sequence, 0.0, 1.0)


def test_invalid_sample_types_and_projection_rejected() -> None:
    with pytest.raises(TypeError, match="screening"):
        _sample(1, 0.0, 1.0, screening="gas")
    with pytest.raises(TypeError, match="samples"):
        coalesce_wits0_fluid_screening([object()], source_key=SOURCE, axis=AXIS)
    with pytest.raises(ValueError, match="source_key"):
        _sample(1, 0.0, 1.0, source_key=" ")
    with pytest.raises(ValueError, match="axis"):
        _sample(1, 0.0, 1.0, axis="depth")


def test_reordered_or_overlapping_coverage_fails_closed() -> None:
    with pytest.raises(ValueError, match="sequences"):
        _coalesce(_sample(2, 0.0, 1.0), _sample(2, 1.0, 2.0))
    with pytest.raises(ValueError, match="sequences"):
        _coalesce(_sample(3, 0.0, 1.0), _sample(2, 1.0, 2.0))
    with pytest.raises(ValueError, match="non-overlapping"):
        _coalesce(_sample(1, 0.0, 1.0), _sample(2, 0.9, 2.0))


def test_empty_input_and_immutable_observations() -> None:
    assert _coalesce() == ()
    sample = _sample(1, 0.0, 1.0)
    with pytest.raises(FrozenInstanceError):
        sample.start = 2.0
    interval = _coalesce(sample)[0]
    with pytest.raises(FrozenInstanceError):
        interval.end = 2.0


def _source_session(
    *,
    session_id: str = "session-1",
    domain: DepthDomain = DepthDomain.MD,
    kind: IndexType = IndexType.MD,
    role: IndexRole = IndexRole.DEPTH,
    unit: str = "m",
    position: float = 2500.5,
    source: str = "wits0:record=02;raw-sha256=" + "a" * 64,
) -> tuple[AcquisitionSession, AcquisitionRecord]:
    index = AcquisitionIndexSchema(
        index_id="verified-index",
        mnemonic="MD" if domain is DepthDomain.MD else "ELAPSED",
        index_type=kind,
        role=role,
        unit=unit,
    )
    schema = AcquisitionDatasetSchema(
        dataset_id="wits-dataset",
        name="WITS",
        kind=DatasetKind.GTI,
        depth_domain=domain,
        indexes=(index,),
        active_index_id="verified-index",
        curves=(),
    )
    record = AcquisitionRecord(
        record_id="wits0-row-1",
        sequence=1,
        kind=AcquisitionRecordKind.DATA_ROW,
        payload=AcquisitionDataRowPayload(
            index_values=(("verified-index", position),), curve_values=()
        ),
        received_at="2026-10-31T00:00:00Z",
        source=source,
    )
    return (
        AcquisitionSession(
            session_id=session_id,
            well_id="well-1",
            dataset_schema=schema,
            records=[record],
        ),
        record,
    )


def test_source_point_binding_reads_exact_wits_md_row_without_fabricating_interval() -> None:
    session, record = _source_session()
    screening = _projection()
    point = bind_wits0_fluid_screening_point(
        session, record, axis=Wits0GasContextAxis.DEPTH, screening=screening
    )
    assert isinstance(point, Wits0FluidScreeningPoint)
    assert point.source_identity == ("well-1", "session-1", "wits-dataset")
    assert (point.record_id, point.sequence, point.position) == (
        "wits0-row-1", 1, 2500.5
    )
    assert point.record_source == record.source
    assert point.screening is screening
    assert point.axis is Wits0GasContextAxis.DEPTH
    # Point data does not contain an invented coverage end or yield intervals.
    assert not hasattr(point, "end")
    with pytest.raises(TypeError, match="samples"):
        coalesce_wits0_fluid_screening(
            (point,), source_key=SOURCE, axis=AXIS
        )
    with pytest.raises(FrozenInstanceError):
        point.position = 2501.0


def test_source_point_binding_supports_only_verified_relative_seconds() -> None:
    session, record = _source_session(
        domain=DepthDomain.TIME,
        kind=IndexType.RELATIVE_TIME,
        role=IndexRole.TIME,
        unit="s",
        position=90.0,
    )
    point = bind_wits0_fluid_screening_point(
        session,
        record,
        axis=Wits0GasContextAxis.ELAPSED_TIME,
        screening=_projection(),
    )
    assert point.position == 90.0
    assert point.axis is Wits0GasContextAxis.ELAPSED_TIME
    assert point.source_identity[1] == session.session_id


@pytest.mark.parametrize(
    "domain,kind,role,unit,axis",
    [
        (DepthDomain.MD, IndexType.MD, IndexRole.DEPTH, "ft", Wits0GasContextAxis.DEPTH),
        (DepthDomain.TVD, IndexType.TVD, IndexRole.DEPTH, "m", Wits0GasContextAxis.DEPTH),
        (
            DepthDomain.TIME,
            IndexType.DATETIME,
            IndexRole.TIME,
            "s",
            Wits0GasContextAxis.ELAPSED_TIME,
        ),
        (
            DepthDomain.TIME,
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "ms",
            Wits0GasContextAxis.ELAPSED_TIME,
        ),
        (DepthDomain.TIME, IndexType.RELATIVE_TIME, IndexRole.TIME, "s", Wits0GasContextAxis.DEPTH),
    ],
)
def test_source_point_binding_rejects_unverified_axis_and_units(
    domain: DepthDomain,
    kind: IndexType,
    role: IndexRole,
    unit: str,
    axis: Wits0GasContextAxis,
) -> None:
    session, record = _source_session(
        domain=domain, kind=kind, role=role, unit=unit
    )
    with pytest.raises(ValueError, match="axis/unit"):
        bind_wits0_fluid_screening_point(
            session, record, axis=axis, screening=_projection()
        )


def test_source_point_binding_rejects_foreign_and_non_wits_rows() -> None:
    session, record = _source_session()
    foreign, _ = _source_session(session_id="other-session")
    with pytest.raises(ValueError, match="belong"):
        bind_wits0_fluid_screening_point(
            foreign, record, axis=AXIS, screening=_projection()
        )
    other, other_row = _source_session(source="etp12:record=02")
    with pytest.raises(ValueError, match="WITS0"):
        bind_wits0_fluid_screening_point(
            other, other_row, axis=AXIS, screening=_projection()
        )
    with pytest.raises(TypeError, match="screening"):
        bind_wits0_fluid_screening_point(
            session, record, axis=AXIS, screening="oil"
        )


def _record_bound_point() -> tuple[AcquisitionSession, Wits0FluidScreeningPoint]:
    session, record = _source_session()
    point = bind_wits0_fluid_screening_point(
        session, record, axis=AXIS, screening=_projection()
    )
    return session, point


def test_acquisition_bound_point_stays_valid_when_its_row_is_unchanged() -> None:
    session, point = _record_bound_point()
    assert verify_wits0_fluid_screening_point(session, point) is None
    assert verify_wits0_fluid_screening_point(session, point) is None
    assert point.position == 2500.5
    assert not hasattr(point, "end")


def test_acquisition_bound_point_rejects_changed_coordinate() -> None:
    session, point = _record_bound_point()
    record = session.records[0]
    session.records[0] = replace(
        record,
        payload=AcquisitionDataRowPayload(
            index_values=(("verified-index", 2501.0),),
            curve_values=(),
        ),
    )
    with pytest.raises(ValueError, match="no longer matches"):
        verify_wits0_fluid_screening_point(session, point)


def test_acquisition_bound_point_rejects_changed_raw_audit_reference() -> None:
    session, point = _record_bound_point()
    record = session.records[0]
    session.records[0] = replace(
        record,
        source="wits0:record=02;raw-sha256=" + "b" * 64,
    )
    with pytest.raises(ValueError, match="no longer matches"):
        verify_wits0_fluid_screening_point(session, point)


@pytest.mark.parametrize(
    "record_change,reason",
    [
        ({"record_id": "replacement-row"}, "missing or duplicated"),
        ({"sequence": 2}, "no longer matches"),
        ({"source": "etp12:record=02"}, "WITS0"),
    ],
)
def test_acquisition_bound_point_rejects_replaced_record(
    record_change: dict[str, object], reason: str
) -> None:
    session, point = _record_bound_point()
    session.records[0] = replace(session.records[0], **record_change)
    with pytest.raises(ValueError, match=reason):
        verify_wits0_fluid_screening_point(session, point)


def test_acquisition_bound_point_rejects_missing_or_duplicate_rows() -> None:
    session, point = _record_bound_point()
    session.records.clear()
    with pytest.raises(ValueError, match="missing or duplicated"):
        verify_wits0_fluid_screening_point(session, point)

    session, point = _record_bound_point()
    session.records.append(session.records[0])
    with pytest.raises(ValueError, match="missing or duplicated"):
        verify_wits0_fluid_screening_point(session, point)


def test_acquisition_bound_point_rejects_foreign_source_and_axis_change() -> None:
    session, point = _record_bound_point()
    foreign, _record = _source_session(session_id="other-session")
    with pytest.raises(ValueError, match="another acquisition source"):
        verify_wits0_fluid_screening_point(foreign, point)
    with pytest.raises(ValueError, match="axis/unit"):
        verify_wits0_fluid_screening_point(
            session, replace(point, axis=Wits0GasContextAxis.ELAPSED_TIME)
        )
    with pytest.raises(TypeError, match="point"):
        verify_wits0_fluid_screening_point(session, "not-a-point")
    with pytest.raises(TypeError, match="session"):
        verify_wits0_fluid_screening_point("not-a-session", point)


def test_acquisition_bound_point_rejects_changed_active_index_unit() -> None:
    session, point = _record_bound_point()
    index = session.dataset_schema.indexes[0]
    session.dataset_schema = replace(
        session.dataset_schema,
        indexes=(replace(index, unit="ft"),),
    )
    with pytest.raises(ValueError, match="axis/unit"):
        verify_wits0_fluid_screening_point(session, point)


def _screening_point_sequence(
) -> tuple[AcquisitionSession, tuple[Wits0FluidScreeningPoint, ...]]:
    session, first = _source_session()
    second = replace(
        first,
        record_id="wits0-row-2",
        sequence=2,
        payload=AcquisitionDataRowPayload(
            index_values=(("verified-index", 2501.0),), curve_values=()
        ),
    )
    third = replace(
        first,
        record_id="wits0-row-3",
        sequence=3,
        payload=AcquisitionDataRowPayload(
            index_values=(("verified-index", 2498.5),), curve_values=()
        ),
    )
    session.records.extend((second, third))
    screening = _projection()
    points = tuple(
        bind_wits0_fluid_screening_point(
            session, record, axis=AXIS, screening=screening
        )
        for record in session.records
    )
    return session, points


def test_source_point_snapshot_preserves_observed_gaps_and_reverse_md() -> None:
    session, points = _screening_point_sequence()
    # Sequence 2 is intentionally absent from the requested point selection;
    # no measurement width or interval can be inferred from sequence numbers.
    selected = (points[0], points[2])
    result = snapshot_wits0_fluid_screening_points(session, iter(selected))
    assert result == selected
    assert tuple(point.position for point in result) == (2500.5, 2498.5)
    assert tuple(point.sequence for point in result) == (1, 3)
    assert all(not hasattr(point, "end") for point in result)
    assert snapshot_wits0_fluid_screening_points(session, ()) == ()


def test_source_point_snapshot_rejects_changed_row_before_publishing() -> None:
    session, points = _screening_point_sequence()
    second = session.records[1]
    session.records[1] = replace(
        second,
        payload=AcquisitionDataRowPayload(
            index_values=(("verified-index", 2600.0),),
            curve_values=(),
        ),
    )
    with pytest.raises(ValueError, match="no longer matches"):
        snapshot_wits0_fluid_screening_points(session, points)
    session, points = _screening_point_sequence()
    third = session.records[2]
    session.records[2] = replace(
        third,
        source="wits0:record=02;raw-sha256=" + "b" * 64,
    )
    with pytest.raises(ValueError, match="no longer matches"):
        snapshot_wits0_fluid_screening_points(session, points)


def test_source_point_snapshot_rejects_unordered_or_repeated_samples() -> None:
    session, points = _screening_point_sequence()
    with pytest.raises(ValueError, match="increase strictly"):
        snapshot_wits0_fluid_screening_points(session, (points[2], points[0]))
    with pytest.raises(ValueError, match="must not repeat"):
        snapshot_wits0_fluid_screening_points(session, (points[0], points[0]))
    with pytest.raises(TypeError, match="points"):
        snapshot_wits0_fluid_screening_points(session, (points[0], object()))


def test_source_point_snapshot_rejects_foreign_missing_and_duplicate_rows() -> None:
    session, points = _screening_point_sequence()
    foreign, _row = _source_session(session_id="foreign-session")
    with pytest.raises(ValueError, match="another acquisition source"):
        snapshot_wits0_fluid_screening_points(foreign, points)
    session.records.pop()
    with pytest.raises(ValueError, match="missing or duplicated"):
        snapshot_wits0_fluid_screening_points(session, points)
    session, points = _screening_point_sequence()
    session.records.append(session.records[2])
    with pytest.raises(ValueError, match="missing or duplicated"):
        snapshot_wits0_fluid_screening_points(session, points)


def test_source_point_snapshot_rejects_mixed_axes_and_units() -> None:
    session, points = _screening_point_sequence()
    with pytest.raises(ValueError, match="cannot mix"):
        snapshot_wits0_fluid_screening_points(
            session,
            (points[0], replace(points[1], axis=Wits0GasContextAxis.ELAPSED_TIME)),
        )
    index = session.dataset_schema.indexes[0]
    session.dataset_schema = replace(
        session.dataset_schema,
        indexes=(replace(index, unit="ft"),),
    )
    with pytest.raises(ValueError, match="axis/unit"):
        snapshot_wits0_fluid_screening_points(session, points)
    with pytest.raises(TypeError, match="session"):
        snapshot_wits0_fluid_screening_points("not-a-session", points)
