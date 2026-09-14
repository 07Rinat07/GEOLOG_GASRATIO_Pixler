from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from geoworkbench.domain.localized_content import normalize_content_language


class TranslationState(StrEnum):
    MISSING = "missing"
    DRAFT = "draft"
    REVIEWED = "reviewed"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class TranslationStatus:
    """Persisted readiness of one language variant of one authored field."""

    state: TranslationState
    source_language: str
    source_revision: int
    translation_revision: int = 0
    dependency_revisions: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_language",
            normalize_content_language(self.source_language, allow_undetermined=True),
        )
        if (
            isinstance(self.source_revision, bool)
            or not isinstance(self.source_revision, int)
            or self.source_revision < 0
        ):
            raise ValueError("Ревизия исходного текста должна быть неотрицательной")
        if (
            isinstance(self.translation_revision, bool)
            or not isinstance(self.translation_revision, int)
            or self.translation_revision < 0
        ):
            raise ValueError("Ревизия перевода должна быть неотрицательной")
        for dependency, revision in self.dependency_revisions.items():
            if not dependency.strip():
                raise ValueError("ID зависимости перевода не может быть пустым")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                raise ValueError("Ревизия зависимости должна быть неотрицательной")
