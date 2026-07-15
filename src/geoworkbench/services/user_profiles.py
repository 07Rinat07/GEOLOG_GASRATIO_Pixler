from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QSettings


@dataclass(frozen=True, slots=True)
class EngineerProfile:
    profile_id: str
    display_name: str
    organization: str = ""


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
        next_active = profiles[0].profile_id if active and active.profile_id == profile_id and profiles else (
            active.profile_id if active else None
        )
        self._store(profiles, next_active)

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
