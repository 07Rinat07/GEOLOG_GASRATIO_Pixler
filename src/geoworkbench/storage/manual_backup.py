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


@dataclass(frozen=True, slots=True)
class VerifiedBackupEntry:
    """An archive member whose saved bytes match the manifest."""

    path: str
    name: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class VerifiedBackup:
    """Read-only inventory; does not authorize extraction or restoration."""

    created_at: str
    entries: tuple[VerifiedBackupEntry, ...]
    total_bytes: int


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


    def inspect(self, source: Path, *, max_total_bytes: int = 64 * 1024**3) -> VerifiedBackup:
        """Verify a v1 manual ZIP without extracting, writing, or trusting its names.

        The limit bounds total uncompressed payload bytes; the writer uses ZIP_STORED.
        This is an integrity check of the supplied archive, not source authentication
        or a restore operation. It does not lock the archive against concurrent edits.
        """
        if type(max_total_bytes) is not int or max_total_bytes <= 0:
            raise BackupError("Invalid backup inspection byte limit")
        source = Path(source)
        try:
            with source.open("rb") as stream:
                before = os.fstat(stream.fileno())
                with ZipFile(stream, "r") as archive:
                    members = archive.infolist()
                    if not 2 <= len(members) <= 1001:
                        raise BackupError("Invalid backup entry count")
                    names = [member.filename for member in members]
                    if len(names) != len(set(names)) or names.count("manifest.json") != 1:
                        raise BackupError("Duplicate or missing backup manifest/member")
                    for member in members:
                        if (member.is_dir() or member.compress_type != ZIP_STORED
                                or member.flag_bits & 1
                                or member.file_size < 0):
                            raise BackupError("Unsupported or unsafe backup member")
                    manifest_info = archive.getinfo("manifest.json")
                    if manifest_info.file_size > 1024 * 1024:
                        raise BackupError("Backup manifest exceeds size limit")

                    def unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
                        result: dict[str, object] = {}
                        for key, value in pairs:
                            if key in result:
                                raise BackupError("Duplicate backup manifest key")
                            result[key] = value
                        return result

                    manifest = json.loads(
                        archive.read(manifest_info).decode("utf-8"),
                        object_pairs_hook=unique_keys,
                    )
                    if (not isinstance(manifest, dict)
                            or set(manifest) != {"format", "version", "created_at", "entries"}
                            or manifest["format"] != "geolog-manual-backup"
                            or type(manifest["version"]) is not int or manifest["version"] != 1
                            or not isinstance(manifest["created_at"], str)
                            or not isinstance(manifest["entries"], list)):
                        raise BackupError("Unsupported backup manifest")
                    timestamp = datetime.fromisoformat(manifest["created_at"])
                    if timestamp.tzinfo is None:
                        raise BackupError("Backup timestamp must have a timezone")
                    rows = manifest["entries"]
                    if not 1 <= len(rows) <= 1000 or len(rows) != len(members) - 1:
                        raise BackupError("Backup inventory does not match archive")
                    verified: list[VerifiedBackupEntry] = []
                    total = 0
                    paths: set[str] = set()
                    for row in rows:
                        if not isinstance(row, dict) or set(row) != {"path", "name", "size", "sha256"}:
                            raise BackupError("Invalid backup inventory row")
                        path, name, size, digest = (row["path"], row["name"],
                                                    row["size"], row["sha256"])
                        if (not isinstance(path, str) or not isinstance(name, str)
                                or not name or len(name) > 255 or "/" in name or "\\" in name
                                or type(size) is not int or size < 0
                                or not isinstance(digest, str) or len(digest) != 64
                                or any(c not in "0123456789abcdef" for c in digest)):
                            raise BackupError("Invalid backup member metadata")
                        project = (path.startswith("projects/")
                                   and len(path) == len("projects/0001.geologpkg")
                                   and path[9:13].isdigit()
                                   and path.endswith(".geologpkg")
                                   and name.casefold().endswith(".geologpkg"))
                        if not (project or path == "settings/preferences.ini"):
                            raise BackupError("Unexpected backup member path")
                        if path in paths or path not in names:
                            raise BackupError("Duplicate or missing backup member")
                        paths.add(path)
                        member = archive.getinfo(path)
                        total += member.file_size
                        if total > max_total_bytes or size != member.file_size:
                            raise BackupError("Backup exceeds byte limit or manifest size differs")
                        with archive.open(member, "r") as payload:
                            actual_digest, actual_size = self._copy(payload, None)
                        if actual_digest != digest or actual_size != size:
                            raise BackupError("Backup member checksum mismatch")
                        verified.append(VerifiedBackupEntry(path, name, size, digest))
                    if paths != set(names) - {"manifest.json"}:
                        raise BackupError("Unlisted backup member")
                after = os.fstat(stream.fileno())
            if self._identity(before) != self._identity(after) or self._identity(before) != self._identity(source.stat()):
                raise BackupError("Backup changed during inspection")
            return VerifiedBackup(manifest["created_at"], tuple(verified), total)
        except (OSError, BadZipFile, ValueError, TypeError, KeyError, UnicodeError) as exc:
            raise BackupError(f"Cannot inspect backup: {exc}") from exc
