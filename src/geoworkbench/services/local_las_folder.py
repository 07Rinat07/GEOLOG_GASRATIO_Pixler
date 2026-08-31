from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import stat


class LocalLasFolderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LocalLasCandidate:
    path: Path
    relative_path: str
    size_bytes: int
    modified_at: str
    sha256: str


class LocalLasFolderProvider:
    """Read-only LAS source backed by a locally synchronized directory."""

    provider_kind = "local_synced_folder"

    def __init__(
        self,
        root: str | Path,
        *,
        recursive: bool = False,
        max_file_size: int = 512 * 1024**2,
    ) -> None:
        self.root = Path(root)
        self.recursive = bool(recursive)
        if isinstance(max_file_size, bool) or not isinstance(max_file_size, int) or max_file_size < 1:
            raise ValueError("max_file_size должен быть положительным целым")
        self.max_file_size = max_file_size

    def discover(self) -> tuple[LocalLasCandidate, ...]:
        root = self._validated_root()
        iterator = root.rglob("*") if self.recursive else root.iterdir()
        candidates: list[LocalLasCandidate] = []
        try:
            paths = sorted(iterator, key=lambda item: str(item).casefold())
        except OSError as exc:
            raise LocalLasFolderError(f"Не удалось прочитать синхронизируемую папку: {root}") from exc
        for path in paths:
            if path.suffix.casefold() != ".las":
                continue
            candidates.append(self._inspect(path, root))
        return tuple(
            sorted(
                candidates,
                key=lambda item: (item.modified_at, item.relative_path.casefold()),
                reverse=True,
            )
        )

    def verify(self, candidate: LocalLasCandidate) -> LocalLasCandidate:
        root = self._validated_root()
        current = self._inspect(candidate.path, root)
        if current != candidate:
            raise LocalLasFolderError(
                f"LAS изменился после обнаружения: {candidate.relative_path}"
            )
        return current

    def _validated_root(self) -> Path:
        try:
            before = self.root.stat()
            root = self.root.resolve(strict=True)
        except OSError as exc:
            raise LocalLasFolderError(
                f"Синхронизируемая папка не найдена: {self.root}"
            ) from exc
        if not stat.S_ISDIR(before.st_mode):
            raise LocalLasFolderError(f"Источник LAS не является папкой: {self.root}")
        return root

    def _inspect(self, path: Path, root: Path) -> LocalLasCandidate:
        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(root):
                raise LocalLasFolderError(f"LAS находится вне синхронизируемой папки: {path}")
            before = path.lstat()
        except OSError as exc:
            raise LocalLasFolderError(f"Не удалось прочитать LAS: {path}") from exc
        if not stat.S_ISREG(before.st_mode) or path.is_symlink():
            raise LocalLasFolderError(f"LAS должен быть обычным файлом: {path}")
        if before.st_size > self.max_file_size:
            raise LocalLasFolderError(
                f"LAS превышает лимит {self.max_file_size // (1024**2)} МБ: {path.name}"
            )
        digest = sha256()
        try:
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            after = path.lstat()
        except OSError as exc:
            raise LocalLasFolderError(f"Не удалось прочитать LAS: {path}") from exc
        if not stat.S_ISREG(after.st_mode) or (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ino != after.st_ino
        ):
            raise LocalLasFolderError(f"LAS изменился во время чтения: {path.name}")
        modified = datetime.fromtimestamp(
            after.st_mtime, tz=timezone.utc
        ).isoformat().replace("+00:00", "Z")
        return LocalLasCandidate(
            path=resolved,
            relative_path=resolved.relative_to(root).as_posix(),
            size_bytes=after.st_size,
            modified_at=modified,
            sha256=digest.hexdigest(),
        )
