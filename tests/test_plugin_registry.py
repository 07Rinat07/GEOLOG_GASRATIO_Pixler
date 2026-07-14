from pathlib import Path

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.plugins import (
    PLUGIN_API_VERSION,
    CalculationRequest,
    CalculationResult,
    PluginMetadata,
    PluginRegistrationError,
    PluginRegistry,
)


class TestImporter:
    metadata = PluginMetadata("test.las", "Test LAS", "1.0.0")

    def supported_extensions(self) -> tuple[str, ...]:
        return (".las",)

    def probe(self, path: Path) -> float:
        return 1.0 if path.suffix.casefold() == ".las" else 0.0

    def import_data(self, path: Path) -> Dataset:
        return Dataset(
            "dataset-1",
            path.stem,
            DatasetKind.GTI,
            DepthDomain.MD,
            np.array([1.0]),
        )


class TestCalculation:
    metadata = PluginMetadata("test.ratio", "Test Ratio", "1.2.0")

    def required_inputs(self) -> tuple[str, ...]:
        return ("A", "B")

    def calculate(self, request: CalculationRequest) -> CalculationResult:
        return CalculationResult({"RATIO": request.inputs["A"] / request.inputs["B"]})


def test_registry_registers_and_returns_typed_plugins() -> None:
    registry = PluginRegistry()
    importer = TestImporter()
    calculation = TestCalculation()

    registry.register_importer(importer)
    registry.register_calculation(calculation)

    assert registry.importers.get("test.las") is importer
    result = registry.calculations.get("test.ratio").calculate(
        CalculationRequest({"A": np.array([4.0]), "B": np.array([2.0])})
    )
    np.testing.assert_allclose(result.curves["RATIO"], [2.0])


def test_registry_rejects_duplicate_plugin_in_same_category() -> None:
    registry = PluginRegistry()
    registry.register_importer(TestImporter())

    with pytest.raises(PluginRegistrationError, match="уже зарегистрирован"):
        registry.register_importer(TestImporter())


@pytest.mark.parametrize("plugin_id", ["", "UPPER", "has space", ".prefix"])
def test_registry_rejects_invalid_plugin_id(plugin_id: str) -> None:
    importer = TestImporter()
    importer.metadata = PluginMetadata(plugin_id, "Invalid", "1.0.0")

    with pytest.raises(PluginRegistrationError, match="plugin_id"):
        PluginRegistry().register_importer(importer)


def test_registry_rejects_incompatible_api_version() -> None:
    importer = TestImporter()
    importer.metadata = PluginMetadata(
        "test.future",
        "Future plugin",
        "1.0.0",
        api_version="99.0",
    )

    with pytest.raises(PluginRegistrationError, match=PLUGIN_API_VERSION):
        PluginRegistry().register_importer(importer)


def test_registry_rejects_missing_required_method() -> None:
    class IncompleteImporter:
        metadata = PluginMetadata("test.incomplete", "Incomplete", "1.0.0")

        def supported_extensions(self) -> tuple[str, ...]:
            return (".las",)

        def probe(self, path: Path) -> float:
            return 0.0

    with pytest.raises(PluginRegistrationError, match="import_data"):
        PluginRegistry().register_importer(IncompleteImporter())  # type: ignore[arg-type]


def test_unknown_plugin_has_clear_error() -> None:
    with pytest.raises(KeyError, match="missing"):
        PluginRegistry().tracks.get("missing")
