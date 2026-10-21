"""Explicit, bounded-memory backups of saved packages and a settings snapshot."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import IO
from zipfile import ZIP_STORED, BadZipFile, ZipFile


class BackupError(RuntimeError):
    """The requested backup could not be safely completed."""


@dataclass(frozen=True, slots=True)
class BackupSource:
    path: Path
    archive_name: str


@dataclass(frozen=True, slots=True)
class BackupPlan:
    sources: tuple[BackupSource, ...]
    estimated_bytes: int

    @classmethod
    def build(cls, projects: tuple[Path, ...], settings: Path | None = None) -> BackupPlan:
        sources: list[BackupSource] = []
        seen: set[Path] = set()
        for project in projects:
            path = project.resolve(strict=True)
            if path in seen:
                continue
            if path.suffix.casefold() != ".geologpkg" or not path.is_file():
                raise BackupError(f"Expected a saved .geologpkg project: {project}")
            seen.add(path)
            sources.append(BackupSource(path, f"projects/{len(sources) + 1:04d}.geologpkg"))
        if settings is not None:
            path = settings.resolve(strict=True)
            if not path.is_file():
                raise BackupError("Settings snapshot is not a file")
            sources.append(BackupSource(path, "settings/preferences.ini"))
        if not sources:
            raise BackupError("Select at least one project or the settings snapshot")
        return cls(tuple(sources), sum(source.path.stat().st_size for source in sources))


class ManualBackupService:
    """Stream selected files, verify their hashes, then publish without overwrite."""

    block_size = 1024 * 1024

    def create(self, plan: BackupPlan, destination: Path) -> Path:
        destination = Path(destination)
        if destination.exists():
            raise BackupError(f"Backup already exists: {destination}")
        if not plan.sources:
            raise BackupError("Empty backup plan")
        if destination.resolve() in {source.path.resolve() for source in plan.sources}:
            raise BackupError("Backup cannot replace a source file")
        names = [source.archive_name for source in plan.sources]
        if len(set(names)) != len(names) or any(
            name.startswith("/") or ".." in name.split("/") or "\\" in name
            or name == "manifest.json" for name in names
        ):
            raise BackupError("Invalid backup entry names")
        descriptor, name = tempfile.mkstemp(prefix=".geolog-backup-", suffix=".tmp", dir=destination.parent)
        pending = Path(name)
        try:
            with os.fdopen(descriptor, "w+b") as stream:
                with ZipFile(stream, "w", compression=ZIP_STORED, allowZip64=True) as archive:
                    entries: list[dict[str, str | int]] = []
                    for source in plan.sources:
                        with source.path.open("rb") as original:
                            before = os.fstat(original.fileno())
                            with archive.open(source.archive_name, "w", force_zip64=True) as output:
                                digest, size = self._copy(original, output)
                            after = os.fstat(original.fileno())
                        current = source.path.stat()
                        if self._identity(before) != self._identity(after) or self._identity(before) != self._identity(current):
                            raise BackupError(f"Source changed during backup: {source.path}")
                        entries.append({"path": source.archive_name, "name": source.path.name,
                                        "size": size, "sha256": digest})
                    archive.writestr("manifest.json", json.dumps({
                        "format": "geolog-manual-backup", "version": 1,
                        "created_at": datetime.now(timezone.utc).isoformat(), "entries": entries,
                    }, ensure_ascii=False, indent=2).encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            with ZipFile(pending) as archive:
                for entry in entries:
                    with archive.open(str(entry["path"])) as saved:
                        digest, size = self._copy(saved, None)
                    if digest != entry["sha256"] or size != entry["size"]:
                        raise BackupError("Backup verification failed")
            # Exclusive atomic publication: an existing backup is never replaced.
            os.link(pending, destination)
            return destination
        except (OSError, ValueError, BadZipFile) as exc:
            raise BackupError(f"Could not create backup: {exc}") from exc
        finally:
            pending.unlink(missing_ok=True)

    @staticmethod
    def _identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
        return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)

    def _copy(self, source: IO[bytes], target: IO[bytes] | None) -> tuple[str, int]:
        digest = sha256()
        size = 0
        while block := source.read(self.block_size):
            digest.update(block)
            size += len(block)
            if target is not None:
                target.write(block)
        return digest.hexdigest(), size
