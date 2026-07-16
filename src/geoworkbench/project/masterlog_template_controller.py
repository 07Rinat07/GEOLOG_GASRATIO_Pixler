from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from geoworkbench.domain.models import (
    MasterlogColumnTemplate,
    MasterlogTemplate,
    new_id,
)
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

    def add_column(
        self,
        template_id: str,
        *,
        title: str,
        column_type: str,
        width_mm: float,
        curve_mnemonics: list[str] | None = None,
    ) -> MasterlogColumnTemplate:
        template = self._require(template_id)
        column = self._validated_column(
            new_id(), title, column_type, width_mm, curve_mnemonics or []
        )
        template.columns.append(column)
        self._touch(template)
        return column

    def update_column(
        self,
        template_id: str,
        column_id: str,
        *,
        title: str,
        column_type: str,
        width_mm: float,
        curve_mnemonics: list[str],
    ) -> MasterlogColumnTemplate:
        template = self._require(template_id)
        column = self._validated_column(
            column_id, title, column_type, width_mm, curve_mnemonics
        )
        index = self._column_index(template, column_id)
        template.columns[index] = column
        self._touch(template)
        return column

    def remove_column(
        self, template_id: str, column_id: str
    ) -> MasterlogColumnTemplate:
        template = self._require(template_id)
        index = self._column_index(template, column_id)
        column = template.columns.pop(index)
        self._touch(template)
        return column

    def move_column(self, template_id: str, column_id: str, offset: int) -> bool:
        template = self._require(template_id)
        index = self._column_index(template, column_id)
        target = max(0, min(index + offset, len(template.columns) - 1))
        if target == index:
            return False
        template.columns.insert(target, template.columns.pop(index))
        self._touch(template)
        return True

    def _column_index(self, template: MasterlogTemplate, column_id: str) -> int:
        for index, column in enumerate(template.columns):
            if column.column_id == column_id:
                return index
        raise KeyError(f"Колонка мастерлога не найдена: {column_id}")

    @staticmethod
    def _validated_column(
        column_id: str,
        title: str,
        column_type: str,
        width_mm: float,
        curve_mnemonics: list[str],
    ) -> MasterlogColumnTemplate:
        normalized_title = title.strip()
        normalized_type = column_type.strip()
        mnemonics = list(dict.fromkeys(value.strip() for value in curve_mnemonics))
        if not column_id or not normalized_title or not normalized_type:
            raise ValueError("ID, название и тип колонки не могут быть пустыми")
        if isinstance(width_mm, bool) or not isinstance(width_mm, (int, float)):
            raise ValueError("Ширина колонки должна быть числом")
        if not 5.0 <= width_mm <= 200.0:
            raise ValueError("Ширина колонки должна быть от 5 до 200 мм")
        if any(not mnemonic for mnemonic in mnemonics):
            raise ValueError("Мнемоники кривых не могут быть пустыми")
        return MasterlogColumnTemplate(
            column_id,
            normalized_title,
            normalized_type,
            float(width_mm),
            mnemonics,
        )

    def _touch(self, template: MasterlogTemplate) -> None:
        template.version += 1
        self.session.dirty = True

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
