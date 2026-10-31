"""WITS-INTERP-01: no invented coverage or mixed-source fluid intervals."""

from dataclasses import FrozenInstanceError

import pytest

from geoworkbench.services.gas_ratio_interpretation import classify_gas_ratio
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.wits0_fluid_screening import project_wits0_fluid_screening
from geoworkbench.services.wits0_fluid_screening_intervals import (
    Wits0FluidScreeningSample,
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
