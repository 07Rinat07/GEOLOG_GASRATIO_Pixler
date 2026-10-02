from __future__ import annotations

from collections.abc import Iterable


# Raw components, total-gas aliases, normalized curves and interpretation ratios
# are factual sampled observations. Their screen/report presentation uses points
# instead of a connecting polyline so the graphic does not imply values between
# acquisition samples. Relative-gas *_REL curves are excluded because they own a
# separate cumulative 0–100% stacked-area presentation.
_GAS_POINT_EXACT = frozenset(
    {
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
        "IC4",
        "NC4",
        "IC5",
        "NC5",
        "TG",
        "TGAS",
        "TOTALGAS",
        "TOTAL_GAS",
        "TG_CALC",
        "TG_NORM",
        "TG_NORM_CALC",
        "NORMALIZED_TOTAL_GAS",
        "TOTAL_GAS_NORM",
        "NORM_TG",
        "TGNORM",
        "WETNESS",
        "BALANCE",
        "CHARACTER",
        "WH",
        "BH",
        "CH",
        "C1_C2",
        "C1_C3",
        "C2_C3",
        "C1_C2C3",
        "C1_C4",
        "C1_C5",
        "IC4_NC4",
        "IC5_NC5",
        "OPUS_TG_PCT",
        "OPUS3",
        "OPUS4",
        "OPUS_K1_3",
        "OPUS_1_5",
    }
)

GAS_SCREEN_POINT_SIZE_PX = 4.0
GAS_PREVIEW_POINT_RADIUS_PX = 2.8
GAS_PRINT_POINT_RADIUS_PT = 1.35


def _token(value: object) -> str:
    return str(value or "").strip().upper().replace("-", "_").rsplit(":", 1)[-1]


def is_gas_point_mnemonic(value: object) -> bool:
    """Return whether one curve identifier should be presented as sampled points."""

    token = _token(value)
    if not token or token.endswith("_REL"):
        return False
    return (
        token in _GAS_POINT_EXACT
        or token.startswith("PIXLER_")
        or token.startswith("OPUS_")
        or token.endswith("_NORM")
        or token.endswith("_NORM_REF")
    )


def uses_gas_point_presentation(identifiers: Iterable[object]) -> bool:
    """Return True when any source/canonical identifier is a gas observation."""

    return any(is_gas_point_mnemonic(value) for value in identifiers)


__all__ = [
    "GAS_PREVIEW_POINT_RADIUS_PX",
    "GAS_PRINT_POINT_RADIUS_PT",
    "GAS_SCREEN_POINT_SIZE_PX",
    "is_gas_point_mnemonic",
    "uses_gas_point_presentation",
]
