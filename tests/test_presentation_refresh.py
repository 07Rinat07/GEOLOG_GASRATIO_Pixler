from __future__ import annotations

import pytest

from geoworkbench.services.presentation_refresh import (
    PresentationRefreshAccumulator,
    PresentationRefreshIntent,
)


def test_presentation_refresh_accumulator_coalesces_duplicate_intents() -> None:
    accumulator = PresentationRefreshAccumulator()

    assert accumulator.request(PresentationRefreshIntent.PROJECT_TREE)
    assert accumulator.request(PresentationRefreshIntent.WINDOW_TITLE)
    assert accumulator.request(
        PresentationRefreshIntent.PROJECT_TREE
        | PresentationRefreshIntent.WINDOW_TITLE
    )

    batch = accumulator.consume()

    assert batch.intents == (
        PresentationRefreshIntent.PROJECT_TREE
        | PresentationRefreshIntent.WINDOW_TITLE
    )
    assert batch.request_count == 3
    assert not batch.is_empty
    assert accumulator.pending == PresentationRefreshIntent.NONE
    assert accumulator.request_count == 0

    empty = accumulator.consume()
    assert empty.is_empty
    assert empty.request_count == 0


def test_presentation_refresh_accumulator_ignores_none_and_can_clear() -> None:
    accumulator = PresentationRefreshAccumulator()

    assert not accumulator.request(PresentationRefreshIntent.NONE)
    assert accumulator.request_count == 0

    accumulator.request(PresentationRefreshIntent.PROJECT_TREE)
    accumulator.clear()

    assert accumulator.pending == PresentationRefreshIntent.NONE
    assert accumulator.request_count == 0


def test_presentation_refresh_accumulator_rejects_untyped_requests() -> None:
    accumulator = PresentationRefreshAccumulator()

    with pytest.raises(TypeError, match="PresentationRefreshIntent"):
        accumulator.request(1)  # type: ignore[arg-type]
