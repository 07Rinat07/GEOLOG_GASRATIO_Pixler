from pathlib import Path
from typing import Protocol

class ImportPlugin(Protocol):
    plugin_id: str
    plugin_version: str
    api_version: str
    def supported_extensions(self) -> tuple[str,...]: ...
    def probe(self,path: Path) -> float: ...
    def import_data(self,path: Path) -> object: ...

class CalculationPlugin(Protocol):
    plugin_id: str
    plugin_version: str
    api_version: str
    def required_inputs(self) -> tuple[str,...]: ...
    def calculate(self,inputs: dict[str,object],parameters: dict[str,object]) -> dict[str,object]: ...
