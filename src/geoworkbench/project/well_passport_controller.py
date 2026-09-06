from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from geoworkbench.domain.localized_content import bump_language_revision
from geoworkbench.domain.well_passport import (
    CONSTRUCTION_FIELDS,
    DATE_FIELDS,
    LOCALIZED_FIELDS,
    NUMERIC_FIELDS,
    SHARED_TEXT_FIELDS,
    PassportValidationError,
    WellPassport,
    validate_passport,
)
from geoworkbench.printing.header_fields import template_header_values
from geoworkbench.project.session import ProjectSession


@dataclass(frozen=True, slots=True)
class LegacyPassportValue:
    template_id: str
    template_name: str
    value: str


class WellPassportController:
    """Edit one well atomically without rewriting its LAS or legacy templates."""

    def __init__(self, session: ProjectSession) -> None:
        self.session = session
        self._project = session.project
        self._well = session.current_well

    def _require_well(self):
        if (
            self._well is None
            or self.session.project is not self._project
            or self.session.current_well is not self._well
        ):
            raise PassportValidationError("", "The selected well has changed")
        return self._well

    def draft(self) -> WellPassport:
        well = self._require_well()
        return deepcopy(well.passport) if well.passport is not None else WellPassport()

    def legacy_candidates(
        self,
        field_name: str,
        language: str = "ru",
    ) -> tuple[LegacyPassportValue, ...]:
        self._require_well()
        fields = (
            set(LOCALIZED_FIELDS) | set(NUMERIC_FIELDS) | set(DATE_FIELDS) | set(SHARED_TEXT_FIELDS)
        )
        if field_name not in fields:
            return ()
        candidates = []
        for template in self._project.masterlog_templates.values():
            value = template_header_values(template).get(field_name, "").strip()
            if value:
                candidates.append(LegacyPassportValue(template.template_id, template.name, value))
            if field_name not in CONSTRUCTION_FIELDS:
                continue
            for element in template.header_elements:
                if (
                    element.properties.get("field") == field_name
                    or "header." + element.element_id == field_name
                ):
                    text = element.properties.get(
                        "text_" + language,
                        element.properties.get("text", ""),
                    )
                    if isinstance(text, str) and text.strip() and text.strip() != value:
                        candidates.append(
                            LegacyPassportValue(template.template_id, template.name, text.strip())
                        )
        return tuple(candidates)

    def save(self, draft: WellPassport) -> WellPassport:
        well = self._require_well()
        normalized = validate_passport(draft)
        for role, asset_ref in normalized.logo_refs.items():
            if asset_ref and asset_ref not in self.session.image_assets:
                raise PassportValidationError(role, "The selected logo is unavailable")
        previous = well.passport
        if normalized != previous:
            well.passport = normalized
            well.content_revision += 1
            for language in ("ru", "kk", "en"):
                before = (
                    {key: value.get(language) for key, value in previous.texts_i18n.items()}
                    if previous is not None
                    else {}
                )
                after = {key: value.get(language) for key, value in normalized.texts_i18n.items()}
                if before != after:
                    bump_language_revision(well.language_revisions, language)
            self.session.dirty = True
        return deepcopy(normalized)
