from __future__ import annotations

from collections.abc import Callable

from geoworkbench.project.cuttings_controller import (
    AmbiguousCuttingsIntervalError,
    CuttingsIntervalConflictError,
)


def cuttings_interval_error_message(error: Exception, translate: Callable[..., str]) -> str:
    if isinstance(error, CuttingsIntervalConflictError):
        return translate(
            f"cuttings.interval_{error.reason}",
            top=str(error.top_depth).removesuffix(".0"),
            bottom=str(error.bottom_depth).removesuffix(".0"),
        )
    if isinstance(error, AmbiguousCuttingsIntervalError):
        return translate("cuttings.ambiguous_interval")
    return str(error)
