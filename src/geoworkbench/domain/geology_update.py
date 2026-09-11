"""Immutable provenance for source-profile-bound geological additions."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import re


@dataclass(frozen=True, slots=True)
class GeologyUpdateRecord:
    update_id: str
    well_id: str
    source_name: str
    source_sha256: str
    imported_at: str
    profile_json: str
    profile_sha256: str
    well_sha256_before: str
    well_sha256_after: str
    lithology_ids: tuple[str, ...]
    cuttings_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for value in (self.update_id, self.well_id, self.source_name, self.imported_at):
            if not isinstance(value, str) or not value.strip() or len(value) > 2000:
                raise ValueError("Некорректная запись геологического обновления")
        for digest in (self.source_sha256, self.profile_sha256, self.well_sha256_before, self.well_sha256_after):
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Некорректный хэш геологического обновления")
        if not isinstance(self.profile_json, str):
            raise ValueError("Профиль должен быть JSON-строкой")
        payload = self.profile_json.encode("utf-8")
        if len(payload) > 4 * 1024 * 1024 or sha256(payload).hexdigest() != self.profile_sha256:
            raise ValueError("Размер или хэш профиля не совпадает")
        for identities in (self.lithology_ids, self.cuttings_ids):
            if not isinstance(identities, tuple) or len(identities) > 10_000 or not all(
                isinstance(value, str) and 0 < len(value) <= 2000 for value in identities
            ) or len(set(identities)) != len(identities):
                raise ValueError("Некорректные ID геологических интервалов")
        if not self.lithology_ids and not self.cuttings_ids:
            raise ValueError("Пустая запись геологического обновления")
