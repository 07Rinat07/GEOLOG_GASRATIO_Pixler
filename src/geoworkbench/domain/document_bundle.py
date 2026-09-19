from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Iterable


class DocumentBundleContractError(ValueError):
    """Raised when a document-bundle request violates the domain contract."""


class DocumentBundleScopeKind(StrEnum):
    WHOLE_WELL = "whole_well"
    NEW_SECTION = "new_section"
    INTERVAL = "interval"


_SUPPORTED_LANGUAGES = frozenset({"ru", "kk", "en"})
_SUPPORTED_ORIENTATIONS = frozenset({"portrait", "landscape"})


def _normalized_unique_values(
    values: Iterable[str],
    *,
    field_name: str,
) -> tuple[str, ...]:
    normalized = tuple(value.strip() for value in values)
    if not normalized:
        raise DocumentBundleContractError(f"{field_name} must not be empty")
    if any(not value for value in normalized):
        raise DocumentBundleContractError(f"{field_name} must not contain blank values")
    if len(set(normalized)) != len(normalized):
        raise DocumentBundleContractError(f"{field_name} must not contain duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class DocumentBundleScope:
    kind: DocumentBundleScopeKind
    top_depth: float | None = None
    bottom_depth: float | None = None

    def __post_init__(self) -> None:
        if self.kind is DocumentBundleScopeKind.WHOLE_WELL:
            if self.top_depth is not None or self.bottom_depth is not None:
                raise DocumentBundleContractError(
                    "whole-well scope must not define explicit depth bounds"
                )
            return

        if self.top_depth is None or self.bottom_depth is None:
            raise DocumentBundleContractError(
                f"{self.kind.value} scope requires top_depth and bottom_depth"
            )
        if not isfinite(self.top_depth) or not isfinite(self.bottom_depth):
            raise DocumentBundleContractError("depth bounds must be finite")
        if self.bottom_depth <= self.top_depth:
            raise DocumentBundleContractError(
                "bottom_depth must be greater than top_depth"
            )


@dataclass(frozen=True, slots=True)
class DocumentBundleRequest:
    """Validated selection for a future single-revision document bundle."""

    well_id: str
    output_ids: tuple[str, ...]
    languages: tuple[str, ...]
    orientations: tuple[str, ...]
    scope: DocumentBundleScope
    allow_drafts: bool = False

    def __post_init__(self) -> None:
        well_id = self.well_id.strip()
        if not well_id:
            raise DocumentBundleContractError("well_id must not be blank")

        output_ids = _normalized_unique_values(
            self.output_ids,
            field_name="output_ids",
        )
        languages = _normalized_unique_values(
            self.languages,
            field_name="languages",
        )
        orientations = _normalized_unique_values(
            self.orientations,
            field_name="orientations",
        )

        unsupported_languages = set(languages) - _SUPPORTED_LANGUAGES
        if unsupported_languages:
            unsupported = ", ".join(sorted(unsupported_languages))
            raise DocumentBundleContractError(
                f"unsupported bundle languages: {unsupported}"
            )

        unsupported_orientations = set(orientations) - _SUPPORTED_ORIENTATIONS
        if unsupported_orientations:
            unsupported = ", ".join(sorted(unsupported_orientations))
            raise DocumentBundleContractError(
                f"unsupported bundle orientations: {unsupported}"
            )

        object.__setattr__(self, "well_id", well_id)
        object.__setattr__(self, "output_ids", output_ids)
        object.__setattr__(self, "languages", languages)
        object.__setattr__(self, "orientations", orientations)
