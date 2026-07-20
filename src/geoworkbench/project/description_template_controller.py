from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.project.session import ProjectSession


@dataclass(slots=True)
class DescriptionTemplateController:
    session: ProjectSession

    def available(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            sorted(
                self.session.project.description_templates.items(), key=lambda x: x[0].casefold()
            )
        )

    def add(self, name: str, text: str) -> None:
        name, text = self._validate(name, text)
        if name in self.session.project.description_templates:
            raise ValueError(f"Шаблон уже существует: {name}")
        self.session.project.description_templates[name] = text
        self.session.dirty = True

    def update(self, original_name: str, name: str, text: str) -> None:
        if original_name not in self.session.project.description_templates:
            raise KeyError(f"Шаблон не найден: {original_name}")
        name, text = self._validate(name, text)
        if name != original_name and name in self.session.project.description_templates:
            raise ValueError(f"Шаблон уже существует: {name}")
        del self.session.project.description_templates[original_name]
        self.session.project.description_templates[name] = text
        self.session.dirty = True

    def remove(self, name: str) -> None:
        try:
            del self.session.project.description_templates[name]
        except KeyError as exc:
            raise KeyError(f"Шаблон не найден: {name}") from exc
        self.session.dirty = True

    @staticmethod
    def _validate(name: str, text: str) -> tuple[str, str]:
        name, text = name.strip(), text.strip()
        if not name:
            raise ValueError("Название шаблона не может быть пустым")
        if len(name) > 100:
            raise ValueError("Название шаблона не должно превышать 100 символов")
        if not text:
            raise ValueError("Текст шаблона не может быть пустым")
        return name, text
