from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.localized_content import normalize_content_language
from geoworkbench.domain.models import Well
from geoworkbench.project.session import ProjectSession


@dataclass(slots=True)
class AuthoredFieldSourceLanguageController:
    """Session boundary for explicit per-field source-language metadata."""

    session: ProjectSession

    def source_language(self, field_id: str) -> str | None:
        normalized_field_id = self._field_id(field_id)
        return self._require_well().authored_field_source_languages.get(normalized_field_id)

    def set_source_language(self, field_id: str, language: object) -> str:
        well = self._require_well()
        normalized_field_id = self._field_id(field_id)
        language_code = normalize_content_language(language)
        if well.authored_field_source_languages.get(normalized_field_id) == language_code:
            return language_code
        well.authored_field_source_languages[normalized_field_id] = language_code
        self._mark_changed(well)
        return language_code

    def clear_source_language(self, field_id: str) -> bool:
        well = self._require_well()
        normalized_field_id = self._field_id(field_id)
        if normalized_field_id not in well.authored_field_source_languages:
            return False
        del well.authored_field_source_languages[normalized_field_id]
        self._mark_changed(well)
        return True

    @staticmethod
    def _field_id(field_id: str) -> str:
        if not isinstance(field_id, str) or not field_id.strip():
            raise ValueError("ID авторского поля не может быть пустым")
        return field_id.strip()

    def _require_well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        return well

    def _mark_changed(self, well: Well) -> None:
        well.content_revision += 1
        self.session.mark_dirty()
