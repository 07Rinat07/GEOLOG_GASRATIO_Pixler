from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Iterable

from geoworkbench.domain.document_bundle import (
    DocumentBundleOutputFormat,
    DocumentBundleOutputSpec,
    DocumentBundleRequest,
    DocumentBundleScope,
    DocumentBundleScopeKind,
)
from geoworkbench.project.session import ProjectSession


class DocumentBundleSelectionError(ValueError):
    """Raised when UI/API bundle selection cannot form a valid request."""


@dataclass(frozen=True, slots=True)
class DocumentBundleOutputOption:
    output_id: str
    label: str
    exporter_kind: str
    source_id: str
    dataset_id: str
    file_format: DocumentBundleOutputFormat
    target_name: str
    supported_orientations: tuple[str, ...]

    def to_spec(self) -> DocumentBundleOutputSpec:
        return DocumentBundleOutputSpec(
            output_id=self.output_id,
            exporter_kind=self.exporter_kind,
            source_id=self.source_id,
            dataset_id=self.dataset_id,
            file_format=self.file_format,
            target_name=self.target_name,
        )


@dataclass(slots=True)
class DocumentBundleSelectionController:
    """Read-only selection/application boundary for the WELL-06 command UI."""

    session: ProjectSession

    def masterlog_options(
        self,
        *,
        well_id: str,
        dataset_id: str,
    ) -> tuple[DocumentBundleOutputOption, ...]:
        well = self.session.project.wells.get(well_id)
        if well is None:
            raise DocumentBundleSelectionError(f"Unknown well: {well_id}")
        if dataset_id not in well.datasets:
            raise DocumentBundleSelectionError(
                f"Dataset {dataset_id!r} is not part of well {well_id!r}"
            )

        options: list[DocumentBundleOutputOption] = []
        for template in sorted(
            self.session.project.masterlog_templates.values(),
            key=lambda item: (item.name.casefold(), item.template_id),
        ):
            output_id = f"masterlog:{template.template_id}:{dataset_id}"
            target_name = _target_name(
                label=template.name,
                stable_id=output_id,
                suffix=".pdf",
            )
            orientations = (
                ("portrait",)
                if template.page_format.casefold() == "roll"
                else ("portrait", "landscape")
            )
            options.append(
                DocumentBundleOutputOption(
                    output_id=output_id,
                    label=template.name,
                    exporter_kind="masterlog",
                    source_id=template.template_id,
                    dataset_id=dataset_id,
                    file_format=DocumentBundleOutputFormat.PDF,
                    target_name=target_name,
                    supported_orientations=orientations,
                )
            )
        return tuple(options)

    def build_request(
        self,
        *,
        well_id: str,
        selected_outputs: Iterable[DocumentBundleOutputOption],
        languages: Iterable[str],
        orientations: Iterable[str],
        scope_kind: DocumentBundleScopeKind,
        top_depth: float | None = None,
        bottom_depth: float | None = None,
        allow_drafts: bool = False,
    ) -> DocumentBundleRequest:
        outputs = tuple(selected_outputs)
        if not outputs:
            raise DocumentBundleSelectionError(
                "Select at least one document bundle output"
            )
        if any(
            output.dataset_id not in self._well_dataset_ids(well_id)
            for output in outputs
        ):
            raise DocumentBundleSelectionError(
                "All selected outputs must belong to the selected well"
            )

        selected_orientations = _unique_values(orientations, "orientations")
        for output in outputs:
            unsupported = set(selected_orientations) - set(output.supported_orientations)
            if unsupported:
                raise DocumentBundleSelectionError(
                    f"{output.label!r} does not support orientations: "
                    + ", ".join(sorted(unsupported))
                )

        scope = DocumentBundleScope(
            scope_kind,
            top_depth=top_depth,
            bottom_depth=bottom_depth,
        )
        return DocumentBundleRequest(
            well_id=well_id,
            output_ids=tuple(output.output_id for output in outputs),
            languages=_unique_values(languages, "languages"),
            orientations=selected_orientations,
            scope=scope,
            allow_drafts=allow_drafts,
            output_specs=tuple(output.to_spec() for output in outputs),
        )

    def _well_dataset_ids(self, well_id: str) -> frozenset[str]:
        well = self.session.project.wells.get(well_id)
        if well is None:
            raise DocumentBundleSelectionError(f"Unknown well: {well_id}")
        return frozenset(well.datasets)


def _target_name(*, label: str, stable_id: str, suffix: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z._-]+", "-", label.strip()).strip("-.")
    if not slug:
        slug = "document"
    slug = slug[:80]
    digest = sha256(stable_id.encode("utf-8")).hexdigest()[:10]
    return f"{slug}-{digest}{suffix}"


def _unique_values(values: Iterable[str], field_name: str) -> tuple[str, ...]:
    normalized = tuple(value.strip() for value in values)
    if not normalized or any(not value for value in normalized):
        raise DocumentBundleSelectionError(f"{field_name} must not be empty")
    if len(set(normalized)) != len(normalized):
        raise DocumentBundleSelectionError(
            f"{field_name} must not contain duplicates"
        )
    return normalized
