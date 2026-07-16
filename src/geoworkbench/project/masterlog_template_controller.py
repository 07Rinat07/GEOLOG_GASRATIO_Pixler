from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from geoworkbench.domain.models import MasterlogTemplate, new_id
from geoworkbench.project.session import ProjectSession


class MasterlogTemplateController:
    def __init__(self, session: ProjectSession) -> None:
        self.session = session

    def create(self, name: str) -> MasterlogTemplate:
        normalized = self._validate_unique_name(name)
        template = MasterlogTemplate(new_id(), normalized)
        self.session.project.masterlog_templates[template.template_id] = template
        self.session.dirty = True
        return template

    def copy(self, template_id: str, name: str) -> MasterlogTemplate:
        source = self._require(template_id)
        normalized = self._validate_unique_name(name)
        template = replace(
            deepcopy(source),
            template_id=new_id(),
            name=normalized,
            version=1,
        )
        self.session.project.masterlog_templates[template.template_id] = template
        self.session.dirty = True
        return template

    def rename(self, template_id: str, name: str) -> MasterlogTemplate:
        template = self._require(template_id)
        normalized = self._validate_unique_name(name, exclude_id=template_id)
        template.name = normalized
        template.version += 1
        self.session.dirty = True
        return template

    def delete(self, template_id: str) -> MasterlogTemplate:
        template = self._require(template_id)
        del self.session.project.masterlog_templates[template_id]
        self.session.dirty = True
        return template

    def _require(self, template_id: str) -> MasterlogTemplate:
        try:
            return self.session.project.masterlog_templates[template_id]
        except KeyError as exc:
            raise KeyError(f"Шаблон мастерлога не найден: {template_id}") from exc

    def _validate_unique_name(self, name: str, *, exclude_id: str | None = None) -> str:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Имя шаблона мастерлога не может быть пустым")
        if len(normalized) > 200:
            raise ValueError("Имя шаблона мастерлога не должно превышать 200 символов")
        duplicate = any(
            template_id != exclude_id
            and template.name.casefold() == normalized.casefold()
            for template_id, template in self.session.project.masterlog_templates.items()
        )
        if duplicate:
            raise ValueError(f"Шаблон мастерлога уже существует: {normalized}")
        return normalized
