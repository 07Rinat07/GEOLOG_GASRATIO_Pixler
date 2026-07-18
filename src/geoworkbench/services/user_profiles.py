from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QSettings

from geoworkbench.printing.page_settings import (
    PrintOrientation,
    PrintPageFormat,
    PrintPageSettings,
)


@dataclass(frozen=True, slots=True)
class EngineerProfile:
    profile_id: str
    display_name: str
    organization: str = ""


@dataclass(frozen=True, slots=True)
class CursorLineSettings:
    color: str = "#dc2626"
    width: float = 2.0
    enabled: bool = False


@dataclass(slots=True)
class UserProfileSettings:
    settings: Any

    @classmethod
    def system(cls) -> UserProfileSettings:
        return cls(QSettings())

    def profiles(self) -> tuple[EngineerProfile, ...]:
        raw = self.settings.value("users/profiles", "[]")
        try:
            payload = json.loads(str(raw))
        except json.JSONDecodeError:
            return ()
        if not isinstance(payload, list):
            return ()
        profiles: list[EngineerProfile] = []
        seen: set[str] = set()
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                profile = self._validate(EngineerProfile(**item))
            except (TypeError, ValueError):
                continue
            if profile.profile_id not in seen:
                profiles.append(profile)
                seen.add(profile.profile_id)
        return tuple(profiles)

    def active(self) -> EngineerProfile | None:
        active_id = str(self.settings.value("users/active_profile", ""))
        return next((item for item in self.profiles() if item.profile_id == active_id), None)

    def create(self, display_name: str, organization: str = "") -> EngineerProfile:
        profile = self._validate(
            EngineerProfile(str(uuid4()), display_name.strip(), organization.strip())
        )
        self._store((*self.profiles(), profile), profile.profile_id)
        return profile

    def update(self, profile: EngineerProfile) -> EngineerProfile:
        validated = self._validate(profile)
        profiles = list(self.profiles())
        for index, current in enumerate(profiles):
            if current.profile_id == validated.profile_id:
                profiles[index] = validated
                active = self.active()
                self._store(tuple(profiles), active.profile_id if active else None)
                return validated
        raise KeyError(f"Неизвестный профиль: {validated.profile_id}")

    def select(self, profile_id: str) -> EngineerProfile:
        profile = next((item for item in self.profiles() if item.profile_id == profile_id), None)
        if profile is None:
            raise KeyError(f"Неизвестный профиль: {profile_id}")
        self.settings.setValue("users/active_profile", profile.profile_id)
        self.settings.sync()
        return profile

    def delete(self, profile_id: str) -> None:
        profiles = tuple(item for item in self.profiles() if item.profile_id != profile_id)
        if len(profiles) == len(self.profiles()):
            raise KeyError(f"Неизвестный профиль: {profile_id}")
        active = self.active()
        next_active = (
            profiles[0].profile_id
            if active and active.profile_id == profile_id and profiles
            else (active.profile_id if active else None)
        )
        self._store(profiles, next_active)

    def print_page_settings(self) -> PrintPageSettings:
        key = self._print_settings_key()
        raw = self.settings.value(key, "")
        try:
            payload = json.loads(str(raw))
            if not isinstance(payload, dict):
                return PrintPageSettings()
            page_format = payload.get("page_format")
            orientation = payload.get("orientation")
            if not isinstance(page_format, str) or not isinstance(orientation, str):
                return PrintPageSettings()
            return PrintPageSettings(
                PrintPageFormat(page_format),
                PrintOrientation(orientation),
                float(payload.get("custom_width_mm", 210.0)),
                float(payload.get("custom_height_mm", 297.0)),
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            return PrintPageSettings()

    def save_print_page_settings(self, value: PrintPageSettings) -> None:
        if not isinstance(value, PrintPageSettings):
            raise TypeError("Настройки страницы должны использовать PrintPageSettings")
        self.settings.setValue(
            self._print_settings_key(),
            json.dumps(
                {
                    "page_format": value.page_format.value,
                    "orientation": value.orientation.value,
                    "custom_width_mm": value.custom_width_mm,
                    "custom_height_mm": value.custom_height_mm,
                }
            ),
        )
        self.settings.sync()

    def cursor_line_settings(self) -> CursorLineSettings:
        raw = self.settings.value(self._cursor_settings_key(), "")
        try:
            payload = json.loads(str(raw))
            if not isinstance(payload, dict):
                return CursorLineSettings()
            color = str(payload.get("color", "#dc2626"))
            width = float(payload.get("width", 2.0))
            enabled = payload.get("enabled", False)
            if (
                len(color) != 7
                or not color.startswith("#")
                or any(character not in "0123456789abcdefABCDEF" for character in color[1:])
                or not 0.5 <= width <= 10.0
                or not isinstance(enabled, bool)
            ):
                return CursorLineSettings()
            return CursorLineSettings(color.lower(), width, enabled)
        except (json.JSONDecodeError, TypeError, ValueError):
            return CursorLineSettings()

    def save_cursor_line_settings(self, value: CursorLineSettings) -> None:
        if not isinstance(value, CursorLineSettings):
            raise TypeError("Настройки визира должны использовать CursorLineSettings")
        self.settings.setValue(
            self._cursor_settings_key(), json.dumps(asdict(value), ensure_ascii=False)
        )
        self.settings.sync()

    def _print_settings_key(self) -> str:
        active = self.active()
        profile_id = active.profile_id if active is not None else "default"
        return f"users/print_page/{profile_id}"

    def _cursor_settings_key(self) -> str:
        active = self.active()
        profile_id = active.profile_id if active is not None else "default"
        return f"users/cursor_line/{profile_id}"

    def _store(self, profiles: tuple[EngineerProfile, ...], active_id: str | None) -> None:
        self.settings.setValue(
            "users/profiles",
            json.dumps([asdict(item) for item in profiles], ensure_ascii=False),
        )
        if active_id:
            self.settings.setValue("users/active_profile", active_id)
        else:
            self.settings.remove("users/active_profile")
        self.settings.sync()

    @staticmethod
    def _validate(profile: EngineerProfile) -> EngineerProfile:
        if not profile.profile_id.strip() or len(profile.profile_id) > 128:
            raise ValueError("Некорректный ID профиля")
        if not profile.display_name.strip() or len(profile.display_name) > 200:
            raise ValueError("Имя инженера обязательно и не должно превышать 200 символов")
        if len(profile.organization) > 300:
            raise ValueError("Название организации не должно превышать 300 символов")
        return profile
