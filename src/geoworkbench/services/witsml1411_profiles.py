from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

from geoworkbench.importers.witsml1411.models import Witsml1411ConnectionProfile


_PROFILE_SCHEMA = "geoworkbench.witsml1411-profiles.v1"
_ALLOWED_ROOT = {"schema", "profiles"}


@dataclass(slots=True)
class Witsml1411ProfileStore:
    path: Path

    def load_all(self) -> tuple[Witsml1411ConnectionProfile, ...]:
        if not self.path.exists():
            return ()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or set(payload).difference(_ALLOWED_ROOT):
            raise ValueError("Invalid WITSML 1.4.1.1 profile file")
        if payload.get("schema") != _PROFILE_SCHEMA:
            raise ValueError("Unsupported WITSML 1.4.1.1 profile schema")
        profiles = payload.get("profiles")
        if not isinstance(profiles, list):
            raise ValueError("WITSML profile list is missing")
        result = tuple(Witsml1411ConnectionProfile.from_public_dict(item) for item in profiles)
        ids = [item.profile_id for item in result]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate WITSML profile IDs")
        return result

    def save_all(self, profiles: Iterable[Witsml1411ConnectionProfile]) -> None:
        items = tuple(profiles)
        ids = [item.profile_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate WITSML profile IDs")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": _PROFILE_SCHEMA,
            "profiles": [item.to_public_dict() for item in sorted(items, key=lambda value: value.name.casefold())],
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def upsert(self, profile: Witsml1411ConnectionProfile) -> None:
        profiles = {item.profile_id: item for item in self.load_all()}
        profiles[profile.profile_id] = profile
        self.save_all(profiles.values())

    def delete(self, profile_id: str) -> None:
        self.save_all(item for item in self.load_all() if item.profile_id != profile_id)
