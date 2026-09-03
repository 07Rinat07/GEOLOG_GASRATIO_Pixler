from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
from typing import Any

from geoworkbench.storage.project_codec import ProjectFormatError


STORAGE_FORMAT = "geolog-chunked-json"
STORAGE_VERSION = 1
STORAGE_MARKER = "$geolog_storage"
CHUNK_DIRECTORY = "chunks"


class ChunkedProjectDocumentError(ProjectFormatError):
    """Raised when chunked project storage cannot be encoded or reconstructed safely."""


@dataclass(frozen=True, slots=True)
class ChunkedStorageDescriptor:
    format: str = STORAGE_FORMAT
    version: int = STORAGE_VERSION
    chunk_count: int = 0
    chunked_list_count: int = 0
    value_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "format": self.format,
            "version": self.version,
            "chunk_count": self.chunk_count,
            "chunked_list_count": self.chunked_list_count,
            "value_count": self.value_count,
        }


class ChunkedProjectDocumentCodec:
    """Externalize large scalar JSON arrays into deterministic package chunks."""

    def __init__(self, *, chunk_threshold: int = 8_192, chunk_size: int = 65_536) -> None:
        if isinstance(chunk_threshold, bool) or chunk_threshold <= 0:
            raise ValueError("chunk_threshold must be a positive integer")
        if isinstance(chunk_size, bool) or chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")
        self.chunk_threshold = int(chunk_threshold)
        self.chunk_size = int(chunk_size)

    def encode(self, project_path: Path, package_root: Path) -> ChunkedStorageDescriptor:
        project_file = Path(project_path)
        root = Path(package_root)
        document = self._read_document(project_file)
        chunk_directory = root / CHUNK_DIRECTORY
        chunk_directory.mkdir(parents=True, exist_ok=True)

        state = _EncodingState()
        encoded = self._externalize(document, root=root, state=state)
        self._write_json(project_file, encoded, indent=2)

        if state.chunk_count == 0:
            chunk_directory.rmdir()
        return ChunkedStorageDescriptor(
            chunk_count=state.chunk_count,
            chunked_list_count=state.chunked_list_count,
            value_count=state.value_count,
        )

    def decode(self, project_path: Path, package_root: Path) -> ChunkedStorageDescriptor:
        project_file = Path(project_path)
        root = Path(package_root)
        document = self._read_document(project_file)
        state = _DecodingState()
        decoded = self._hydrate(document, root=root, state=state)
        self._write_json(project_file, decoded, indent=2)
        return ChunkedStorageDescriptor(
            chunk_count=state.chunk_count,
            chunked_list_count=state.chunked_list_count,
            value_count=state.value_count,
        )

    def _externalize(self, value: Any, *, root: Path, state: _EncodingState) -> Any:
        if isinstance(value, dict):
            return {
                key: self._externalize(item, root=root, state=state)
                for key, item in value.items()
            }
        if isinstance(value, list):
            if len(value) >= self.chunk_threshold and all(self._is_scalar(item) for item in value):
                return self._write_chunks(value, root=root, state=state)
            return [self._externalize(item, root=root, state=state) for item in value]
        return value

    def _write_chunks(
        self,
        values: list[object],
        *,
        root: Path,
        state: _EncodingState,
    ) -> dict[str, object]:
        descriptors: list[dict[str, object]] = []
        for start in range(0, len(values), self.chunk_size):
            chunk_values = values[start : start + self.chunk_size]
            state.chunk_count += 1
            relative = f"{CHUNK_DIRECTORY}/{state.chunk_count:08d}.json"
            chunk_path = root.joinpath(*PurePosixPath(relative).parts)
            chunk_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_json(chunk_path, chunk_values, indent=None)
            descriptors.append({"path": relative, "count": len(chunk_values)})
        state.chunked_list_count += 1
        state.value_count += len(values)
        return {
            STORAGE_MARKER: {
                "kind": "scalar-list",
                "version": STORAGE_VERSION,
                "count": len(values),
                "chunks": descriptors,
            }
        }

    def _hydrate(self, value: Any, *, root: Path, state: _DecodingState) -> Any:
        if self._is_chunk_reference(value):
            return self._read_chunks(value[STORAGE_MARKER], root=root, state=state)
        if isinstance(value, dict):
            return {key: self._hydrate(item, root=root, state=state) for key, item in value.items()}
        if isinstance(value, list):
            return [self._hydrate(item, root=root, state=state) for item in value]
        return value

    def _read_chunks(
        self,
        reference: dict[str, object],
        *,
        root: Path,
        state: _DecodingState,
    ) -> list[object]:
        if set(reference) != {"kind", "version", "count", "chunks"}:
            raise ChunkedProjectDocumentError("Ссылка на chunk содержит неизвестные поля")
        if reference.get("kind") != "scalar-list" or reference.get("version") != STORAGE_VERSION:
            raise ChunkedProjectDocumentError("Версия chunked storage не поддерживается")
        expected_count = self._non_negative_int(reference.get("count"), "count")
        raw_chunks = reference.get("chunks")
        if not isinstance(raw_chunks, list) or not raw_chunks:
            raise ChunkedProjectDocumentError("Ссылка на chunk не содержит chunks")

        values: list[object] = []
        seen_paths: set[str] = set()
        for raw_chunk in raw_chunks:
            if not isinstance(raw_chunk, dict) or set(raw_chunk) != {"path", "count"}:
                raise ChunkedProjectDocumentError("Описание chunk некорректно")
            relative = raw_chunk.get("path")
            if not isinstance(relative, str):
                raise ChunkedProjectDocumentError("Путь chunk отсутствует")
            self._validate_chunk_path(relative)
            if relative in seen_paths:
                raise ChunkedProjectDocumentError(f"Chunk используется повторно: {relative}")
            seen_paths.add(relative)
            declared_count = self._non_negative_int(raw_chunk.get("count"), "chunk count")
            chunk_path = root.joinpath(*PurePosixPath(relative).parts)
            try:
                chunk_values = json.loads(chunk_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ChunkedProjectDocumentError(f"Не удалось прочитать chunk: {relative}") from exc
            if not isinstance(chunk_values, list) or not all(
                self._is_scalar(item) for item in chunk_values
            ):
                raise ChunkedProjectDocumentError(f"Chunk содержит недопустимые значения: {relative}")
            if len(chunk_values) != declared_count:
                raise ChunkedProjectDocumentError(f"Размер chunk не совпадает с описанием: {relative}")
            values.extend(chunk_values)
            state.chunk_count += 1

        if len(values) != expected_count:
            raise ChunkedProjectDocumentError("Общий размер chunked списка не совпадает с описанием")
        state.chunked_list_count += 1
        state.value_count += len(values)
        return values

    @staticmethod
    def validate_descriptor(raw: object) -> ChunkedStorageDescriptor:
        if not isinstance(raw, dict):
            raise ChunkedProjectDocumentError("Manifest не содержит описание storage")
        if set(raw) != {"format", "version", "chunk_count", "chunked_list_count", "value_count"}:
            raise ChunkedProjectDocumentError("Описание storage в manifest некорректно")
        if raw.get("format") != STORAGE_FORMAT or raw.get("version") != STORAGE_VERSION:
            raise ChunkedProjectDocumentError("Версия storage в manifest не поддерживается")
        return ChunkedStorageDescriptor(
            chunk_count=ChunkedProjectDocumentCodec._non_negative_int(
                raw.get("chunk_count"), "chunk_count"
            ),
            chunked_list_count=ChunkedProjectDocumentCodec._non_negative_int(
                raw.get("chunked_list_count"), "chunked_list_count"
            ),
            value_count=ChunkedProjectDocumentCodec._non_negative_int(
                raw.get("value_count"), "value_count"
            ),
        )

    @staticmethod
    def _read_document(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ChunkedProjectDocumentError(f"Не удалось прочитать JSON проекта: {path}") from exc

    @staticmethod
    def _write_json(path: Path, value: Any, *, indent: int | None) -> None:
        try:
            path.write_text(
                json.dumps(value, ensure_ascii=False, indent=indent, separators=None if indent else (",", ":")),
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError) as exc:
            raise ChunkedProjectDocumentError(f"Не удалось записать JSON проекта: {path}") from exc

    @staticmethod
    def _is_chunk_reference(value: Any) -> bool:
        return (
            isinstance(value, dict)
            and set(value) == {STORAGE_MARKER}
            and isinstance(value.get(STORAGE_MARKER), dict)
        )

    @staticmethod
    def _is_scalar(value: object) -> bool:
        return value is None or isinstance(value, (str, bool, int, float))

    @staticmethod
    def _non_negative_int(value: object, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ChunkedProjectDocumentError(f"Поле {field} должно быть неотрицательным целым")
        return value

    @staticmethod
    def _validate_chunk_path(value: str) -> None:
        if not value or "\\" in value or "\x00" in value:
            raise ChunkedProjectDocumentError("Chunk содержит недопустимый путь")
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "." in path.parts
            or len(path.parts) != 2
            or path.parts[0] != CHUNK_DIRECTORY
            or path.suffix != ".json"
        ):
            raise ChunkedProjectDocumentError(f"Chunk содержит небезопасный путь: {value}")


@dataclass(slots=True)
class _EncodingState:
    chunk_count: int = 0
    chunked_list_count: int = 0
    value_count: int = 0


@dataclass(slots=True)
class _DecodingState:
    chunk_count: int = 0
    chunked_list_count: int = 0
    value_count: int = 0
