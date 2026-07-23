import pytest

from geoworkbench.services.startup_timing import (
    DEFAULT_SPLASH_MINIMUM_VISIBLE_MS,
    remaining_splash_delay_ms,
)


def test_default_splash_minimum_visibility_is_three_seconds() -> None:
    assert DEFAULT_SPLASH_MINIMUM_VISIBLE_MS == 3_000


def test_remaining_splash_delay_honours_elapsed_time() -> None:
    assert remaining_splash_delay_ms(minimum_visible_ms=3_000, elapsed_ms=0) == 3_000
    assert remaining_splash_delay_ms(minimum_visible_ms=3_000, elapsed_ms=1_250) == 1_750
    assert remaining_splash_delay_ms(minimum_visible_ms=3_000, elapsed_ms=3_000) == 0
    assert remaining_splash_delay_ms(minimum_visible_ms=3_000, elapsed_ms=4_000) == 0


@pytest.mark.parametrize("field", ["minimum", "elapsed"])
@pytest.mark.parametrize("value", [True, 1.5, "3000", None])
def test_remaining_splash_delay_rejects_non_integer_values(field: str, value: object) -> None:
    kwargs = {"minimum_visible_ms": 3_000, "elapsed_ms": 0}
    kwargs["minimum_visible_ms" if field == "minimum" else "elapsed_ms"] = value
    with pytest.raises(TypeError):
        remaining_splash_delay_ms(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("minimum_visible_ms", "elapsed_ms"),
    [(-1, 0), (3_000, -1)],
)
def test_remaining_splash_delay_rejects_negative_values(
    minimum_visible_ms: int, elapsed_ms: int
) -> None:
    with pytest.raises(ValueError):
        remaining_splash_delay_ms(
            minimum_visible_ms=minimum_visible_ms,
            elapsed_ms=elapsed_ms,
        )
