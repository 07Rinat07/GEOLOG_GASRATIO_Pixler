from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ImportSourceKind(StrEnum):
    LAS = "las"
    CSV = "csv"
    EXCEL = "excel"
    PARADOX = "paradox"


@dataclass(frozen=True, slots=True)
class ImportSourceChoice:
    kind: ImportSourceKind
    label: str


class ImportJobPort(Protocol):
    def execute_import(self, kind: ImportSourceKind) -> None: ...

    def report_unknown_source(self, selected_label: str) -> None: ...


_SOURCE_LABEL_KEYS = (
    (ImportSourceKind.LAS, "import.source_las"),
    (ImportSourceKind.CSV, "import.source_csv"),
    (ImportSourceKind.EXCEL, "import.source_excel"),
    (ImportSourceKind.PARADOX, "import.source_paradox"),
)


class ImportJobController:
    """Resolve one universal-import choice into a stable import job kind."""

    def __init__(self, port: ImportJobPort) -> None:
        self._port = port

    @staticmethod
    def choices(localize: Callable[[str], str]) -> tuple[ImportSourceChoice, ...]:
        return tuple(
            ImportSourceChoice(kind, localize(label_key))
            for kind, label_key in _SOURCE_LABEL_KEYS
        )

    def dispatch(
        self,
        selected_label: str,
        accepted: bool,
        localize: Callable[[str], str],
    ) -> bool:
        if not accepted:
            return False
        kind_by_label = {
            choice.label: choice.kind
            for choice in self.choices(localize)
        }
        kind = kind_by_label.get(selected_label)
        if kind is None:
            self._port.report_unknown_source(selected_label)
            return False
        self._port.execute_import(kind)
        return True
