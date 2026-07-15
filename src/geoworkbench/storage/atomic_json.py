from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from geoworkbench.domain.models import Project
from geoworkbench.data.lossless_las import LosslessLasDocument
from geoworkbench.storage.source_artifacts import save_source_documents
from geoworkbench.storage.project_codec import PROJECT_FORMAT_VERSION
from geoworkbench.tablet.layout_codec import layout_to_dict
from geoworkbench.tablet.models import TabletLayout


def _default(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"Неподдерживаемый тип: {type(value)!r}")


def save_project(
    project: Project,
    target: Path,
    *,
    tablet_layouts: dict[str, TabletLayout] | None = None,
    source_documents: dict[str, LosslessLasDocument] | None = None,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    documents = source_documents or {}
    dataset_ids = {
        dataset_id for well in project.wells.values() for dataset_id in well.datasets
    }
    unknown_document_ids = set(documents) - dataset_ids
    if unknown_document_ids:
        unknown = ", ".join(sorted(unknown_document_ids))
        raise ValueError(f"Source document ссылается на неизвестный набор: {unknown}")
    source_artifacts = save_source_documents(target, documents)
    document = {
        "format_version": PROJECT_FORMAT_VERSION,
        "project": asdict(project),
        "tablet_layouts": {
            dataset_id: layout_to_dict(layout)
            for dataset_id, layout in (tablet_layouts or {}).items()
        },
        "source_artifacts": source_artifacts,
    }
    payload = json.dumps(document, ensure_ascii=False, indent=2, default=_default)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, target)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
