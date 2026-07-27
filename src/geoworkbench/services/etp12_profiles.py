from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

from geoworkbench.importers.etp12.models import Etp12ConnectionProfile


_FORMAT = "geolog-etp12-profiles"
_VERSION = 1
_ALLOWED_ROOT = {"format", "version", "profiles"}
_ALLOWED_PROFILE = {
    "profile_id", "name", "endpoint", "auth_mode", "username", "credential_id",
    "verify_tls", "allow_insecure_localhost", "ca_file", "open_timeout_seconds",
    "request_timeout_seconds", "close_timeout_seconds", "ping_interval_seconds",
    "ping_timeout_seconds", "max_message_bytes", "request_acknowledgement", "reconnect",
}
_ALLOWED_RETRY = {
    "max_attempts", "initial_backoff_seconds", "max_backoff_seconds", "multiplier"
}


class Etp12ProfileStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load_all(self) -> tuple[Etp12ConnectionProfile, ...]:
        if not self.path.exists():
            return ()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, Mapping) or set(data).difference(_ALLOWED_ROOT):
            raise ValueError("Invalid ETP profile document")
        if data.get("format") != _FORMAT or int(data.get("version", 0)) != _VERSION:
            raise ValueError("Unsupported ETP profile document version")
        rows = data.get("profiles", [])
        if not isinstance(rows, list):
            raise ValueError("ETP profiles must be an array")
        profiles: list[Etp12ConnectionProfile] = []
        ids: set[str] = set()
        for row in rows:
            if not isinstance(row, Mapping) or set(row).difference(_ALLOWED_PROFILE):
                raise ValueError("ETP profile contains unknown fields")
            retry = row.get("reconnect", {})
            if not isinstance(retry, Mapping) or set(retry).difference(_ALLOWED_RETRY):
                raise ValueError("ETP reconnect policy contains unknown fields")
            profile = Etp12ConnectionProfile.from_public_dict(row)
            if profile.profile_id in ids:
                raise ValueError(f"Duplicate ETP profile ID: {profile.profile_id}")
            ids.add(profile.profile_id)
            profiles.append(profile)
        return tuple(profiles)

    def upsert(self, profile: Etp12ConnectionProfile) -> None:
        profiles = {item.profile_id: item for item in self.load_all()}
        profiles[profile.profile_id] = profile
        self._save(tuple(sorted(profiles.values(), key=lambda item: item.name.casefold())))

    def delete(self, profile_id: str) -> None:
        profiles = tuple(item for item in self.load_all() if item.profile_id != profile_id)
        self._save(profiles)

    def _save(self, profiles: tuple[Etp12ConnectionProfile, ...]) -> None:
        payload = {
            "format": _FORMAT,
            "version": _VERSION,
            "profiles": [item.to_public_dict() for item in profiles],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
