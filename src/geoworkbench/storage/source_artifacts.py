from __future__ import annotations

import os
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any

from geoworkbench.data.lossless_las import LosslessLasDocument, parse_lossless_las


class SourceArtifactError(RuntimeError):
    pass


def save_source_documents(
    project_path: Path,
    documents: dict[str, LosslessLasDocument],
) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    if not documents:
        return manifest
    assets = _assets_directory(project_path)
    if assets.is_symlink():
        raise SourceArtifactError("Каталог source artifacts не может быть символической ссылкой")
    assets.mkdir(parents=True, exist_ok=True)
    for dataset_id, document in documents.items():
        digest = document.sha256
        artifact = assets / f"{digest}.las"
        if artifact.exists():
            _verify_existing_artifact(artifact, document)
        else:
            _atomic_write(artifact, document.to_bytes())
        manifest[dataset_id] = {
            "path": artifact.relative_to(project_path.parent).as_posix(),
            "sha256": digest,
            "size_bytes": document.size_bytes,
        }
    return manifest


def load_source_documents(
    project_path: Path,
    manifest: dict[str, Any],
) -> dict[str, LosslessLasDocument]:
    documents: dict[str, LosslessLasDocument] = {}
    raw_assets = _assets_directory(project_path)
    if raw_assets.is_symlink():
        raise SourceArtifactError("Каталог source artifacts не может быть символической ссылкой")
    assets = raw_assets.resolve(strict=False)
    for dataset_id, raw_reference in manifest.items():
        if not isinstance(dataset_id, str) or not dataset_id:
            raise SourceArtifactError("Идентификатор source artifact должен быть строкой")
        reference = validate_artifact_reference(raw_reference)
        relative_path = Path(reference["path"])
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise SourceArtifactError(f"Недопустимый путь source artifact: {relative_path}")
        artifact = (project_path.parent / relative_path).resolve(strict=False)
        if not artifact.is_relative_to(assets):
            raise SourceArtifactError(
                f"Source artifact находится вне каталога проекта: {relative_path}"
            )
        if not artifact.is_file():
            raise SourceArtifactError(f"Source artifact не найден: {relative_path}")
        raw_bytes = artifact.read_bytes()
        if len(raw_bytes) != reference["size_bytes"]:
            raise SourceArtifactError(f"Размер source artifact не совпадает: {relative_path}")
        if sha256(raw_bytes).hexdigest() != reference["sha256"]:
            raise SourceArtifactError(f"SHA-256 source artifact не совпадает: {relative_path}")
        documents[dataset_id] = parse_lossless_las(raw_bytes)
    return documents


def validate_artifact_manifest(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SourceArtifactError("Поле 'source_artifacts' должно быть объектом")
    for dataset_id, reference in raw.items():
        if not isinstance(dataset_id, str) or not dataset_id:
            raise SourceArtifactError("Идентификатор source artifact должен быть строкой")
        validate_artifact_reference(reference)
    return raw


def validate_artifact_reference(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SourceArtifactError("Описание source artifact должно быть объектом")
    path = raw.get("path")
    digest = raw.get("sha256")
    size_bytes = raw.get("size_bytes")
    if not isinstance(path, str) or not path:
        raise SourceArtifactError("Путь source artifact отсутствует или некорректен")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise SourceArtifactError("SHA-256 source artifact имеет неверный формат")
    if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
        raise SourceArtifactError("Размер source artifact имеет неверный формат")
    return raw


def _assets_directory(project_path: Path) -> Path:
    return project_path.parent / f"{project_path.name}.assets"


def _verify_existing_artifact(artifact: Path, document: LosslessLasDocument) -> None:
    existing = artifact.read_bytes()
    if len(existing) != document.size_bytes or sha256(existing).hexdigest() != document.sha256:
        raise SourceArtifactError(f"Существующий source artifact повреждён: {artifact.name}")


def _atomic_write(target: Path, payload: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, target)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise
