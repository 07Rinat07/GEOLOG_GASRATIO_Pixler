from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from geoworkbench.domain.document_bundle import (
    DocumentBundleOutputFormat,
    DocumentBundleOutputSpec,
    DocumentBundleRequest,
    DocumentBundleScope,
    DocumentBundleScopeKind,
)
from geoworkbench.domain.models import (
    Dataset,
    DatasetKind,
    DepthDomain,
    MasterlogTemplate,
    Project,
    Well,
)
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)
from geoworkbench.project.document_bundle_snapshot_reader import (
    LoadedDocumentBundleSnapshot,
)
from geoworkbench.project.masterlog_bundle_exporter import (
    MasterlogBundleExportError,
    MasterlogPdfBundleExporter,
)
from geoworkbench.storage.project_codec import ProjectDocument


@dataclass
class StaticSnapshotLoader:
    loaded: LoadedDocumentBundleSnapshot
    calls: int = 0

    def load(
        self,
        _binding: DocumentBundleSnapshotBinding,
    ) -> LoadedDocumentBundleSnapshot:
        self.calls += 1
        return self.loaded


@dataclass
class RecordingRenderer:
    calls: list[tuple[MasterlogTemplate, Path, float, float, str]]

    def __call__(
        self,
        template: MasterlogTemplate,
        _session,
        target: Path,
        *,
        overwrite: bool,
        settings,
    ) -> Path:
        assert overwrite is False
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"%PDF-test")
        self.calls.append(
            (
                template,
                target,
                settings.depth_top,
                settings.depth_bottom,
                settings.language.value,
            )
        )
        return target


def _dataset() -> Dataset:
    return Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1000.0, 1050.0, 1100.0], dtype=np.float64),
    )


def _snapshot(
    tmp_path: Path,
    *,
    scope: DocumentBundleScope | None = None,
    orientation: str = "portrait",
    exporter_kind: str = "masterlog",
    file_format: DocumentBundleOutputFormat = DocumentBundleOutputFormat.PDF,
    dataset_id: str | None = "dataset-1",
    template_page_format: str = "A4",
) -> tuple[DocumentBundleSnapshotBinding, LoadedDocumentBundleSnapshot]:
    output = DocumentBundleOutputSpec(
        output_id="masterlog",
        exporter_kind=exporter_kind,
        source_id="template-1",
        dataset_id=dataset_id,
        file_format=file_format,
        target_name="masterlog.pdf" if file_format is DocumentBundleOutputFormat.PDF else "masterlog.docx",
    )
    request = DocumentBundleRequest(
        well_id="well-1",
        output_ids=("masterlog",),
        languages=("ru",),
        orientations=(orientation,),
        scope=scope or DocumentBundleScope(DocumentBundleScopeKind.WHOLE_WELL),
        output_specs=(output,),
    )
    binding = DocumentBundleSnapshotBinding(
        snapshot_id="1" * 32,
        request=request,
        project_path=tmp_path / "project.geologpkg",
        project_id="project-1",
        save_revision=4,
        well_content_revision=9,
        storage_kind="package",
        path_id="a" * 64,
        bundle_sha256="b" * 64,
    )
    dataset = _dataset()
    well = Well(
        "well-1",
        "Well",
        datasets={dataset.dataset_id: dataset},
        content_revision=9,
    )
    template = MasterlogTemplate(
        "template-1",
        "Masterlog",
        page_format=template_page_format,
    )
    project = Project(
        "project-1",
        "Project",
        wells={well.well_id: well},
        masterlog_templates={template.template_id: template},
        save_revision=4,
    )
    loaded = LoadedDocumentBundleSnapshot(
        binding=binding,
        document=ProjectDocument(project),
    )
    return binding, loaded


def test_masterlog_bundle_exporter_reuses_existing_renderer_on_saved_snapshot(
    tmp_path: Path,
) -> None:
    binding, loaded = _snapshot(tmp_path)
    loader = StaticSnapshotLoader(loaded)
    renderer = RecordingRenderer([])
    exporter = MasterlogPdfBundleExporter(
        output_id="masterlog",
        output_directory=tmp_path / "bundle",
        snapshot_loader=loader,
        renderer=renderer,
    )

    paths = exporter.export(binding)

    assert loader.calls == 1
    assert paths == (tmp_path / "bundle" / "masterlog.pdf",)
    assert paths[0].read_bytes() == b"%PDF-test"
    assert len(renderer.calls) == 1
    template, target, top, bottom, language = renderer.calls[0]
    assert target == paths[0]
    assert (top, bottom, language) == (1000.0, 1100.0, "ru")
    assert template.properties["orientation"] == "portrait"
    assert loaded.document.project.masterlog_templates["template-1"].properties == {}


def test_masterlog_bundle_exporter_uses_bound_interval_and_orientation(
    tmp_path: Path,
) -> None:
    binding, loaded = _snapshot(
        tmp_path,
        scope=DocumentBundleScope(
            DocumentBundleScopeKind.INTERVAL,
            top_depth=1020.0,
            bottom_depth=1080.0,
        ),
        orientation="landscape",
    )
    renderer = RecordingRenderer([])
    exporter = MasterlogPdfBundleExporter(
        output_id="masterlog",
        output_directory=tmp_path,
        snapshot_loader=StaticSnapshotLoader(loaded),
        renderer=renderer,
    )

    exporter.export(binding)

    template, _target, top, bottom, _language = renderer.calls[0]
    assert (top, bottom) == (1020.0, 1080.0)
    assert template.properties["orientation"] == "landscape"


def test_masterlog_bundle_exporter_rejects_roll_landscape(
    tmp_path: Path,
) -> None:
    binding, loaded = _snapshot(
        tmp_path,
        orientation="landscape",
        template_page_format="roll",
    )
    exporter = MasterlogPdfBundleExporter(
        output_id="masterlog",
        output_directory=tmp_path,
        snapshot_loader=StaticSnapshotLoader(loaded),
        renderer=RecordingRenderer([]),
    )

    with pytest.raises(MasterlogBundleExportError, match="portrait"):
        exporter.export(binding)


@pytest.mark.parametrize(
    ("exporter_kind", "file_format", "dataset_id", "message"),
    (
        ("report", DocumentBundleOutputFormat.PDF, "dataset-1", "not a Masterlog"),
        ("masterlog", DocumentBundleOutputFormat.DOCX, "dataset-1", "PDF format"),
        ("masterlog", DocumentBundleOutputFormat.PDF, None, "dataset_id"),
        ("masterlog", DocumentBundleOutputFormat.PDF, "missing", "not present"),
    ),
)
def test_masterlog_bundle_exporter_rejects_incompatible_bound_spec(
    tmp_path: Path,
    exporter_kind: str,
    file_format: DocumentBundleOutputFormat,
    dataset_id: str | None,
    message: str,
) -> None:
    binding, loaded = _snapshot(
        tmp_path,
        exporter_kind=exporter_kind,
        file_format=file_format,
        dataset_id=dataset_id,
    )
    exporter = MasterlogPdfBundleExporter(
        output_id="masterlog",
        output_directory=tmp_path,
        snapshot_loader=StaticSnapshotLoader(loaded),
        renderer=RecordingRenderer([]),
    )

    with pytest.raises(MasterlogBundleExportError, match=message):
        exporter.export(binding)
