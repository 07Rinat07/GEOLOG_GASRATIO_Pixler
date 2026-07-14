from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from geoworkbench.plugins.api import (
    PLUGIN_API_VERSION,
    CalculationPlugin,
    ExportPlugin,
    ImportPlugin,
    PluginMetadata,
    TrackPlugin,
)


_PLUGIN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
PluginType = TypeVar("PluginType")


class PluginRegistrationError(ValueError):
    """Raised when a plugin violates the public registration contract."""


@dataclass(slots=True)
class _PluginCollection(Generic[PluginType]):
    required_methods: tuple[str, ...]
    plugins: dict[str, PluginType] = field(default_factory=dict)

    def register(self, plugin: PluginType) -> None:
        metadata = _validate_metadata(plugin)
        if metadata.plugin_id in self.plugins:
            raise PluginRegistrationError(f"Плагин уже зарегистрирован: {metadata.plugin_id}")
        for method_name in self.required_methods:
            method = getattr(plugin, method_name, None)
            if not callable(method):
                raise PluginRegistrationError(
                    f"Плагин '{metadata.plugin_id}' не реализует метод '{method_name}'"
                )
        self.plugins[metadata.plugin_id] = plugin

    def get(self, plugin_id: str) -> PluginType:
        try:
            return self.plugins[plugin_id]
        except KeyError as exc:
            raise KeyError(f"Плагин не зарегистрирован: {plugin_id}") from exc

    def all(self) -> tuple[PluginType, ...]:
        return tuple(self.plugins.values())


@dataclass(slots=True)
class PluginRegistry:
    importers: _PluginCollection[ImportPlugin] = field(
        default_factory=lambda: _PluginCollection(("supported_extensions", "probe", "import_data"))
    )
    calculations: _PluginCollection[CalculationPlugin] = field(
        default_factory=lambda: _PluginCollection(("required_inputs", "calculate"))
    )
    tracks: _PluginCollection[TrackPlugin] = field(
        default_factory=lambda: _PluginCollection(("create_tracks",))
    )
    exporters: _PluginCollection[ExportPlugin] = field(
        default_factory=lambda: _PluginCollection(("supported_extensions", "export"))
    )

    def register_importer(self, plugin: ImportPlugin) -> None:
        self.importers.register(plugin)

    def register_calculation(self, plugin: CalculationPlugin) -> None:
        self.calculations.register(plugin)

    def register_track(self, plugin: TrackPlugin) -> None:
        self.tracks.register(plugin)

    def register_exporter(self, plugin: ExportPlugin) -> None:
        self.exporters.register(plugin)


def _validate_metadata(plugin: object) -> PluginMetadata:
    metadata = getattr(plugin, "metadata", None)
    if not isinstance(metadata, PluginMetadata):
        raise PluginRegistrationError("Плагин должен содержать PluginMetadata")
    if not _PLUGIN_ID_PATTERN.fullmatch(metadata.plugin_id):
        raise PluginRegistrationError(f"Некорректный plugin_id: {metadata.plugin_id!r}")
    if not metadata.name.strip():
        raise PluginRegistrationError("Название плагина не может быть пустым")
    if not metadata.plugin_version.strip():
        raise PluginRegistrationError("Версия плагина не может быть пустой")
    if metadata.api_version != PLUGIN_API_VERSION:
        raise PluginRegistrationError(
            f"Плагин '{metadata.plugin_id}' использует API {metadata.api_version}; "
            f"поддерживается {PLUGIN_API_VERSION}"
        )
    return metadata
