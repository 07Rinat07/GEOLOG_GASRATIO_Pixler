from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Protocol

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import Dataset, Project
from geoworkbench.tablet.models import TabletLayout, TrackDefinition


PLUGIN_API_VERSION = "1.0"
FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class PluginMetadata:
    plugin_id: str
    name: str
    plugin_version: str
    api_version: str = PLUGIN_API_VERSION
    description: str | None = None


@dataclass(frozen=True, slots=True)
class CalculationRequest:
    inputs: Mapping[str, FloatArray]
    parameters: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CalculationResult:
    curves: Mapping[str, FloatArray]
    messages: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TrackRequest:
    dataset: Dataset
    parameters: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExportRequest:
    project: Project
    target: Path
    tablet_layouts: Mapping[str, TabletLayout] = field(default_factory=dict)
    parameters: Mapping[str, object] = field(default_factory=dict)


class ImportPlugin(Protocol):
    metadata: PluginMetadata

    def supported_extensions(self) -> tuple[str, ...]: ...

    def probe(self, path: Path) -> float: ...

    def import_data(self, path: Path) -> Dataset: ...


class CalculationPlugin(Protocol):
    metadata: PluginMetadata

    def required_inputs(self) -> tuple[str, ...]: ...

    def calculate(self, request: CalculationRequest) -> CalculationResult: ...


class TrackPlugin(Protocol):
    metadata: PluginMetadata

    def create_tracks(self, request: TrackRequest) -> list[TrackDefinition]: ...


class ExportPlugin(Protocol):
    metadata: PluginMetadata

    def supported_extensions(self) -> tuple[str, ...]: ...

    def export(self, request: ExportRequest) -> None: ...
